FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN pip install --no-cache-dir ".[crypto]"
RUN useradd -m vorcaro && mkdir -p /app/state && chown vorcaro /app/state
USER vorcaro
# padrão seguro: simulação, nenhuma ordem enviada
ENTRYPOINT ["vorcaro"]
CMD ["run", "--broker", "paper", "--data", "binance", "--universe", "BTCUSDT,ETHUSDT"]
