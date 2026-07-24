import torch.nn as nn

class LSTMRegressor(nn.Module):
    def __init__(self, input_dim,
                 hidden_size=64,
                 num_layers=1,
                 hidden_dense_size=64,
                 activation="LeakyReLU",
                 dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(input_dim, hidden_size,
                            num_layers=num_layers, batch_first=True)
        self.dropout = nn.Dropout(p=dropout)

        # choose activation
        if activation == "ReLU":
            act = nn.ReLU()
        elif activation == "LeakyReLU":
            act = nn.LeakyReLU()
        elif activation == "tanh":
            act = nn.Tanh()
        else:
            raise ValueError("Unsupported activation")

        # regression head
        self.head = nn.Sequential(
            nn.Linear(hidden_size, hidden_dense_size),
            act,
            nn.Linear(hidden_dense_size, 1)  # 1 output: adjusted_generation
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        last = self.dropout(out[:, -1, :])  # take output of last timestep
        return self.head(last)