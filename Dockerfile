FROM python:3.12-slim

# Node.js 20 설치 (프론트엔드 빌드용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium + 시스템 의존성 설치
RUN playwright install --with-deps chromium

# 프론트엔드 의존성 설치 (package.json 변경 시에만 재실행)
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci --prefer-offline

# 프론트엔드 소스 복사 및 빌드
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# 애플리케이션 코드 복사
COPY . .

# 보고서 출력 디렉터리 생성
RUN mkdir -p output/reports

EXPOSE 8001

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
