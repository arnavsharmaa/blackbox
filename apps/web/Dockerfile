FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/
COPY packages/schemas/package.json packages/schemas/
RUN npm ci --no-audit --no-fund

COPY packages/schemas packages/schemas
COPY apps/web apps/web

# Baked into the client bundle at build time.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:22-slim AS run

WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app/node_modules node_modules
COPY --from=build /app/package.json package.json
COPY --from=build /app/apps/web/.next apps/web/.next
COPY --from=build /app/apps/web/package.json apps/web/package.json
COPY --from=build /app/apps/web/next.config.ts apps/web/next.config.ts
COPY --from=build /app/packages/schemas packages/schemas

RUN useradd --create-home blackbox && chown -R blackbox:blackbox /app
USER blackbox

EXPOSE 3000

CMD ["npm", "run", "start", "--workspace", "apps/web"]
