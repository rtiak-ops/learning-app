# ----------------------------------------------------------------------
# インポート
# ----------------------------------------------------------------------
from __future__ import annotations

import json
import logging

import google.generativeai as genai
import openai
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from .. import dependencies, models
from ..limiter import limiter

# ----------------------------------------------------------------------
# AI (LLM) 連携用のルーター
# ----------------------------------------------------------------------

router = APIRouter(prefix="/ai", tags=["AI"])
logger = logging.getLogger(__name__)

class AIRequest(BaseModel):
    title: str

class AIResponse(BaseModel):
    subtasks: list[str]

@router.post("/breakdown", response_model=AIResponse)
@limiter.limit("10/minute")
async def breakdown_task(
    req: AIRequest,
    request: Request,
    current_user: models.User = Depends(dependencies.get_current_user)
):
    """
    タスク分解API:
    ユーザーが入力した「大きなタスク」を、AIが「3〜5個の具体的なサブタスク」に分解して返します。
    """
    if len(req.title) > 200:
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="タスクのタイトルが長すぎます(200文字以内)"
        )
    
    from ..core import config
    openai_api_key = config.OPENAI_API_KEY
    google_api_key = config.GOOGLE_API_KEY
    
    prompt = f"""
    あなたは優秀なタスク管理アシスタントです。
    以下のタスクを達成するための、具体的で実行可能な3〜5個のサブタスクに分解してください。
    出力は必ず JSON の文字配列(List[str])形式だけにしてください。余計な文章は不要です。
    言語は日本語でお願いします。

    タスク: "{req.title}"
    """

    content = ""
    success = False

    if not success and google_api_key and google_api_key != "dummy":
        try:
            genai.configure(api_key=google_api_key)
            # より広範なモデル名を試行するように拡張
            available_models = [
                "gemini-2.5-flash-light", 
                "gemini-2.5-flash", 
                "gemini-3.0-flash",
                "gemini-flash-latest"
            ]
            
            for model_name in available_models:
                try:
                    logger.info(f"Trying Gemini model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    response = await model.generate_content_async(prompt)
                    content = response.text
                    if content:
                        logger.info(f"Successfully generated content using {model_name}")
                        success = True
                        break
                except Exception as model_err:
                    logger.warning(f"Model {model_name} failed: {model_err}")
                    continue
        except Exception as e:
            logger.error(f"Gemini Configuration/API Error: {e}")

    if not success and openai_api_key and openai_api_key != "dummy":
        try:
            client = openai.AsyncOpenAI(api_key=openai_api_key)
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            content = response.choices[0].message.content
            success = True
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI task breakdown is currently unavailable. Configure an AI provider and try again.",
        )

    try:
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "")
        elif "```" in content:
            content = content.replace("```", "")
            
        subtasks = json.loads(content.strip())
        return AIResponse(subtasks=subtasks)
    except Exception as e:
        logger.error(f"JSON Parse Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AIレスポンスの解析に失敗しました。"
        ) from e
