FROM node:20-slim
WORKDIR /app
COPY source/package.json .
RUN npm install
COPY source/ .
EXPOSE 3003
CMD ["npm", "start"]
