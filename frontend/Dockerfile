# Dev image — runs Vite's own dev server with HMR against a
# bind-mounted source tree (see docker-compose.yml), same shape as the
# backend's own Dockerfile (--reload against a bind mount). A leaner
# multi-stage build (nginx serving a static `vite build` output,
# proxying /api/* to the backend) is deferred to Day 29, matching the
# backend's own already-established "dev now, production build later"
# split — this one optimizes for fast local iteration, not image size.
FROM node:20-slim

WORKDIR /app

# Dependencies first so this layer only rebuilds when package*.json
# actually changes, not on every source edit.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
