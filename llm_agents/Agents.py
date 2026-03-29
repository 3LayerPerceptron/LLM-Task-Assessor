from typing import TypedDict, Annotated, List

from dotenv import load_dotenv
from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_mistralai import ChatMistralAI

class State(TypedDict):
    
    assignment: str
    max_grade: float

    solution: str
    
    generator_output: str
    proposed_grade : float

    judge_output: str
    satisfaction: float
    coherence: float
    style: float

    retry_count: int
    final_decision: str

class GeneratorResponse(BaseModel):
    output : str
    proposed_grade : float

class JudgeResponse(BaseModel):
    output : str
    satisfaction : float
    coherence: float
    style: float



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

        judge_opinion = ""
        if state["retry_count"] > 0:
            judge_opinion = f"""

            Обрати внимание судья, который проверял твою обратную связь поставил тебе следующие оценки:
            Все оценки судьи (от 0 до 1, выше - лучше).

            Твоя предыдущая обратная связь:
            {state["generator_output"]}

            Оценка соответствия формальному стилю: {state["style"]}

            Оценка соответствия обратной связи заданию: {state["coherence"]} 

            Общая оценка удовлетворенности судьи: {state["satisfaction"]}

            Комментарий судьи по исправлению обратной связи (ОБРАТИ ВНИМАНИЕ):

            {state["judge_output"]}

            """


        prompt = f"""
            Ты ассистент, проверяющий домашние задания и формирующий обратную связь.
            Твоя задача быть объективным и справедливым.
            Если ты снимаешь баллы, то необходимо пояснить почему.
            Ты общаешься в формальном тоне.

            Задание: 
            {state['assignment']}

            Решение студента: 
            {state['solution']}

            {judge_opinion}

            Макссимальный балл за задание: {state['max_grade']}

            Твоя задача написать короткий но точный комментарий
            Не пиши дополнительно никаких комментариев сразу оцени работу студента.
        """ 
        response = self.generator.invoke(prompt)

        
        return {
            "generator_output": response.output,
            "proposed_grade" : max(0.0, min(response.proposed_grade, state["max_grade"])),
            "retry_count": state["retry_count"] + 1
        }
    

    def judge_node(self, state: State):
        """Judge Agent"""

        prompt = f"""
            Ты ассистент, который контролирует качество обратной связи.
            Твоя задача оценить следующие метрики:
            
            Все оценки (от 0 до 1, выше - лучше)
            Coherence: насколько обратная связь соответствует заданию [0, 1]
            Style: формальность общения, непредвзятость [0, 1]
            Satisfaction: общий скор удовлетворенности, который определяет будет ли принята работа [0, 1]

            Также дай рекоммендации по исправлению
            Помни о том, что задача обратной связи указывать на ошибки, а не решать задание за студента

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
            "coherence": max(0.0, min(response.coherence, 1.0)),
            "style": max(0.0, min(response.style, 1.0)),
            "satisfaction": max(0.0, min(response.satisfaction, 1.0)),
        }

    def retry_loop(self, state: State, threshold=0.7):

        if state["satisfaction"] >= threshold:
            return "end"
        
        if state["retry_count"] < 3:
            return "retry"
        else:
            return "human_review" # Если 3 попытки не помогли -> флаг для человека


    def build(self):
        
        workflow = StateGraph(State)

        workflow.add_node("generator", self.generator_node)
        workflow.add_node("judge", self.judge_node)

        workflow.set_entry_point("generator")
        workflow.add_edge("generator", "judge")

        workflow.add_conditional_edges(
            "judge",
            
            self.retry_loop,
            {
                "end": END,
                "retry": "generator",
                "human_review": END
            }
        )

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
