FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev --ignore-scripts && mkdir /data && chown node:node /data
COPY src ./src
USER node
ENV NODE_ENV=production DATA_DIR=/data
EXPOSE 3000
CMD ["node", "--tls-max-v1.2", "src/main.mjs"]
