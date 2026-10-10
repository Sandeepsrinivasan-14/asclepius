FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
ARG ASCLEPIUS_API_URL=http://api:8000
ENV ASCLEPIUS_API_URL=$ASCLEPIUS_API_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "run", "start"]
