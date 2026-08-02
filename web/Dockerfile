FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci refuses to run here: some deps (lightningcss via Tailwind v4,
# oxlint) ship per-platform prebuilt native binaries as optional
# dependencies, and this lockfile was generated on Windows -- npm ci treats
# the missing Linux-specific optional entries as a hard lockfile mismatch.
# npm install resolves them for the current platform instead of erroring.
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
