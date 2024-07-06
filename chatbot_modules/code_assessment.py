import re
import dspy
from .base_module import BaseChatbotModule

class CodeAssessmentModule(BaseChatbotModule):
    def __init__(self, lm):
        super().__init__(lm)
        self.assess_code = dspy.ChainOfThought("code: str, language: str -> assessment: str")

    def process(self, history, user_input, job_details):
        code_match = re.search(r'```(\w+)\n([\s\S]+?)\n```', user_input)
        if code_match:
            language, code = code_match.groups()
            assessment = self.assess_code(code=code, language=language)
            return f"Code Assessment:\n{assessment.assessment}"
        return None