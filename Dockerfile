FROM python:3.12-slim
WORKDIR /app
COPY opsrag ./opsrag
COPY knowledge ./knowledge
COPY examples ./examples
USER 65532:65532
ENTRYPOINT ["python", "-m", "opsrag"]
CMD ["--input", "examples/sample.json", "--format", "markdown"]
