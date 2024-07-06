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
        self.modules = []

    def add_module(self, module):
        self.modules.append(module(self.lm))

    def process_interaction(self, history, user_input, job_details):
        for module in self.modules:
            response = module.process(history, user_input, job_details)
            if response:
                return response
        return "I'm not sure how to respond to that."