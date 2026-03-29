from backend.src.config import settings
import langgraph
import typing as t
import os
import sys

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_mistralai import ChatMistralAI


# --- Тестовые таски (оставляем как есть) ---
if settings.ENVIRONMENT == "test":
    @settings.CELERY.task(name="awwh")
    def awwh() -> bool:
        return True

    @settings.CELERY.task(name="oops")
    def oops() -> t.NoReturn:
        raise RuntimeError("you know, something wrong happend :(")

# --- ТВОЯ LLM ТАСКА (Грязный хак для импорта) ---
@settings.CELERY.task(name="grade_assignment")
def grade_assignment(assignment: str, solution: str, max_grade: float) -> dict:
    """LLM-based assignment grading task."""
    import os
    import sys
    import logging
    
    logger = logging.getLogger(__name__)
    
    current_file = os.path.abspath(__file__)
    


    for i in range(5):
        current_file = os.path.dirname(current_file)
    project_root = current_file
    
    logger.info(f"Current file: {current_file}")
    logger.info(f"Project root: {project_root}")
    
    # Добавляем корень в sys.path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        logger.info(f"Added to sys.path: {project_root}")
    
    # Проверяем, что llm_agents там есть
    agents_dir = os.path.join(project_root, "llm_agents")
    logger.info(f"Looking for llm_agents at: {agents_dir}")
    logger.info(f"llm_agents exists: {os.path.exists(agents_dir)}")
    
    try:
        from llm_agents import GeneratorJudgeBuilder
        
        builder = GeneratorJudgeBuilder()
        graph = builder.workflow.compile()
        
        initial_state = {
            "assignment": assignment,
            "solution": solution,
            "max_grade": max_grade,
            "generator_output": "",
            "proposed_grade": 0.0,
            "judge_output": "",
            "satisfaction": 0.0,
            "coherence": 0.0,
            "style": 0.0,
            "retry_count": 0,
            "final_decision": ""
        }
        logger.info("Starting LangGraph invocation...")
        result = graph.invoke(initial_state)
        logger.info("LangGraph finished.")
        
        final_decision = "Accepted" if result.get("satisfaction", 0) >= 0.9 else "HumanReview"

        
        
        return {
            "status": "success",
            "generator_output": result.get("generator_output", ""),
            "proposed_grade": result.get("proposed_grade", 0.0),
            "final_decision": final_decision,
            "satisfaction": result.get("satisfaction", 0.0)
        }
        
    except Exception as e:
        logger.error(f"FUCK! LLM Task failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "type": type(e).__name__}

celery = settings.CELERY