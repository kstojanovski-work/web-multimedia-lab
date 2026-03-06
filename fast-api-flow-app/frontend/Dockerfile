FROM node:20-slim AS build

WORKDIR /app

ARG CUSTOM_CA_CERT_BASE64=""

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN if [ -n "$CUSTOM_CA_CERT_BASE64" ]; then \
      echo "$CUSTOM_CA_CERT_BASE64" | base64 -d > /usr/local/share/ca-certificates/custom-root-ca.crt && \
      update-ca-certificates; \
    fi

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_BACKEND_URL=http://localhost:8000
ARG VITE_ICE_SERVERS=""
ARG VITE_TURN_URL=""
ARG VITE_TURN_USERNAME=""
ARG VITE_TURN_CREDENTIAL=""
ENV VITE_BACKEND_URL=${VITE_BACKEND_URL}
ENV VITE_ICE_SERVERS=${VITE_ICE_SERVERS}
ENV VITE_TURN_URL=${VITE_TURN_URL}
ENV VITE_TURN_USERNAME=${VITE_TURN_USERNAME}
ENV VITE_TURN_CREDENTIAL=${VITE_TURN_CREDENTIAL}

RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
