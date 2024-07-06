import dspy
from .base_module import BaseChatbotModule

class PersonalityAssessmentModule(BaseChatbotModule):
    def __init__(self, lm):
        super().__init__(lm)
        self.assess_personality = dspy.ChainOfThought("history: str, user_input: str -> assessment: str")

    def process(self, history, user_input, job_details):
        if "personality assessment" in user_input.lower():
            assessment = self.assess_personality(history=history, user_input=user_input)
            return f"Personality Assessment:\n{assessment.assessment}"
        return None