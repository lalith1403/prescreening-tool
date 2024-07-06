import dspy
from .base_module import BaseChatbotModule

class GeneralConversationModule(BaseChatbotModule):
    def __init__(self, lm):
        super().__init__(lm)
        self.generate_response = dspy.ChainOfThought("history: str, user_input: str, job_details: str -> response: str")

    def process(self, history, user_input, job_details):
        response = self.generate_response(history=history, user_input=user_input, job_details=job_details)
        return response.response