class Planner:
    def __init__(self, llm, token_budget):
        self.llm = llm
        self.token_budget = token_budget

    def propose(self, context, history=""):
        prompt = (
            f"CURRENT ANOMALY CONTEXT:\n{context}\n\n"
            f"PAST INCIDENTS & OUTCOMES:\n{history}\n\n"
            "Propose a safe fix within policy envelope. Do not repeat failed actions."
        )
        return self.llm.generate(prompt, max_tokens=self.token_budget)
