class EWMA:
    def __init__(self, alpha=0.1):
        self.alpha = alpha
        self.mu = None
        self.var = 0.0
        self.sigma = 0.05

    def update(self, x):
        if self.mu is None:
            self.mu = x
            self.var = 0.0
        else:
            diff = x - self.mu
            self.mu += self.alpha * diff
            self.var = (1 - self.alpha) * (self.var + self.alpha * diff**2)
            self.sigma = max(0.01, self.var**0.5)
        return self.mu


def anomalous(x, mu, k=2.5, sigma=0.05):
    if mu is None:
        return False
    return abs(x - mu) > k * sigma
