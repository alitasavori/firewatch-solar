import torch.nn as nn


class MLPRegressor(nn.Module):
    """Simplest sufficient MLP for flattened PV windows (5 days x 6 features = 30)."""

    def __init__(self, input_dim=30, hidden_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x):
        # x: (batch, input_dim)
        return self.net(x)
