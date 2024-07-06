import dspy

class BaseChatbotModule:
    def __init__(self, lm):
        self.lm = lm

    def process(self, history, user_input, job_details):
        raise NotImplementedError("Subclasses must implement this method")

class ModularPrescreeningTool:
    def __init__(self):
        self.lm = dspy.OpenAI(model="gpt-3.5-turbo")
        dspy.settings.configure(lm=self.lm)
        self.generate_response = dspy.ChainOfThought("history: str, user_input: str, job_details: str -> response: str")

    def process_interaction(self, history, user_input, job_details):
        response = self.generate_response(history=history, user_input=user_input, job_details=job_details)
        return response.response