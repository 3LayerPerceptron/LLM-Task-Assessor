from typing import TypedDict, Annotated, List

from dotenv import load_dotenv
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage, SystemMessage

class State(TypedDict):
    
    assignment: str
    max_grade: float

    solution: str
    
    generator_output: str
    proposed_grade : float
    judge_output: str

    retry_count: int
    final_decision: str

class GeneratorResponse(BaseModel):
    output : str
    proposed_grade : float

class JudgeResponse(BaseModel):
    output : str
    satisfaction : float # retry будет работать через порог по satisfaction

class GeneratorJudgeBuilder():
    
    def __init__(self):
        
        self.workflow = self.build()
        
        self.generator = ChatMistralAI(
            model="mistral-medium",
            temperature=0.7
        ).with_structured_output(GeneratorResponse)
        
        self.judge = ChatMistralAI(
            model="mistral-medium",
            temperature=0.1
        ).with_structured_output(JudgeResponse)

    def generator_node(self, state: State):
        """Generator Agent"""
        # Здесь вызов LLM
        prompt = f"""
            Ты ассистент, проверяющий домашние задания и формирующий обратную связь.
            Твоя задача быть объективным и справедливым.
            Если ты снимаешь баллы, то необходимо пояснить почему.
            Ты общаешься в формальном тоне.

            Задание: 
            {state['assignment']}

            Решение студента: 
            {state['solution']}

            Макссимальный балл за задание: {state['max_grade']}

            Твоя задача написать короткий но точный комментарий
            Не пиши дополнительно никаких комментариев сразу оцени работу студента.
        """ 
        response = self.generator.invoke(prompt)
        
        return {
            "generator_output": response.output,
            "proposed_grade" : response.proposed_grade,
            "retry_count": state["retry_count"] + 1
        }
    

    def judge_node(self, state: State):
        """Judge Agent"""

        # Добавим постпроцессинг через Pydantic, это должно решить нашу проблему
        # is_valid = state["satisfaction"] > 0.8 Что-то по типу такого

        prompt = f"""
            Ты ассистент, который контролирует качество обратной связи.
            Твоя задача оценить следующие метрики:

            Coherence: [1, 0]
            Toxicity: [1, 0]

            Также дай рекоммендации по исправлению

            Задание: 
            {state['assignment']}

            Решение студента: 
            {state['solution']}

            Вердикт проверяющего: 
            {state['generator_output']}

            Максимальный балл за задание: {state['max_grade']}
            Балл, который поставил проверяющий: {state['proposed_grade']}

            Твоя задача написать короткий но точный комментарий
            Не пиши дополнительно никаких комментариев сразу оцени качество проверки.
        """

        response = self.judge.invoke(prompt)
        
        return {
            "judge_output": response.output,
            "satisfaction": response.satisfaction
        }

    def should_retry(self, state: State):
        
        # настроить механизм ретраев

        if state["final_decision"] == "Accepted":
            return "end"
        elif state["retry_count"] < 3:
            return "regenerate"
        else:
            return "human_review" # Если 3 попытки не помогли -> флаг для человека


    def build(self):
        
        workflow = StateGraph(State)

        workflow.add_node("generator", self.generator_node)
        workflow.add_node("judge", self.judge_node)

        workflow.set_entry_point("generator")
        workflow.add_edge("generator", "judge")

        ''' Добавить перегенерацию, через SO
        workflow.add_conditional_edges(
            "judge",
            
            self.should_retry,
            {
                "end": END,
                "regenerate": "generator",
                "human_review": END # Понять как добавить
            }
        )
        '''

        return workflow


if __name__ == "__main__":

    load_dotenv()    
    assessor = GeneratorJudgeBuilder().workflow.compile()


    initial_state = {
        "assignment": "Сформулировать 3 цели по SMART",
        "solution": "1. Хорошо поспать 2. Составить список дел на день сегодня в 19:00 3. стать богатым",
        "max_grade" : 15,
        "generator_output": "",
        "verifier_output": "",
        "retry_count": 0,
        "final_decision": ""
    }

    result = assessor.invoke(initial_state)

    print(result["generator_output"])
    print(80 * '#')
    print(result["judge_output"])
