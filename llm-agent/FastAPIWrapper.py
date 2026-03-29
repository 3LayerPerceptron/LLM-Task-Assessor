from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging
from dotenv import load_dotenv

from Agents import GeneratorJudgeBuilder, State

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GradeRequest(BaseModel):
    assignment: str = Field(..., description="Текст задания")
    solution: str = Field(..., description="Решение студента")
    max_grade: float = Field(..., gt=0, description="Максимальный балл за задание")

class GradeResponse(BaseModel):
    generator_output: str = Field(..., description="Итоговый комментарий проверяющего")
    proposed_grade: float = Field(..., description="Рекомендуемая оценка")
    final_decision: str = Field(..., description="Итоговое решение: 'Accepted' или 'HumanReview'")


app = FastAPI(title="Assessor API", description="API для автоматической проверки домашних заданий")
try:
    builder = GeneratorJudgeBuilder()
    graph = builder.workflow.compile()
    logger.info("Граф успешно скомпилирован")
except Exception as e:
    logger.error(f"Ошибка компиляции графа: {e}")
    raise


@app.post("/grade", response_model=GradeResponse)
async def grade_assignment(request: GradeRequest):
    try:
        # Формируем начальное состояние
        initial_state = {
            "assignment": request.assignment,
            "solution": request.solution,
            "max_grade": request.max_grade,
            "generator_output": "",
            "proposed_grade": 0.0,
            "judge_output": "",
            "satisfaction": 0.0,
            "coherence": 0.0,
            "style": 0.0,
            "retry_count": 0,
            "final_decision": ""
        }

        result = graph.invoke(initial_state)

        return GradeResponse(
            generator_output=result.get("generator_output", ""),
            proposed_grade=result.get("proposed_grade", 0.0),
            final_decision=result.get("final_decision", "Unknown"),
        )
    except Exception as e:
        logger.exception("Ошибка при обработке запроса")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)