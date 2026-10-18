FROM node:22-alpine AS deps
WORKDIR /srv/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /srv/web
COPY --from=deps /srv/web/node_modules ./node_modules
COPY apps/web ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine
WORKDIR /srv/web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3010 HOSTNAME=0.0.0.0
COPY --from=build /srv/web/.next/standalone ./
COPY --from=build /srv/web/.next/static ./.next/static
EXPOSE 3010
CMD ["node", "server.js"]
