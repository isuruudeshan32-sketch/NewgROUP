FROM python:3.12-slim
WORKDIR /app
COPY server.py ./
COPY public ./public
RUN useradd --uid 10001 --create-home linka && mkdir /data && chown linka:linka /data
USER linka
ENV DATA_DIR=/data PORT=8080 HOST=0.0.0.0
EXPOSE 8080
VOLUME ["/data"]
CMD ["python", "server.py"]
