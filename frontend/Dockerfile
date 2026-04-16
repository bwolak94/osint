# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# NOTE: Run `npm install` locally first to generate package-lock.json for deterministic builds.
# With a lockfile present, change this to `npm ci` for faster, reproducible installs.
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# Runtime stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
