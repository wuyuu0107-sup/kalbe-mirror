# =========================================================
# 1️⃣ Use official Node image for building
# =========================================================
FROM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files first (for better caching)
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy the rest of your source code
COPY . .

# Build the Next.js app
RUN npm run build

# =========================================================
# 2️⃣ Create lightweight runtime image
# =========================================================
FROM node:20-alpine AS runner

# Set NODE_ENV to production for safety
ENV NODE_ENV=production

# Set working directory
WORKDIR /app

# Copy built app from builder stage
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./

# Install only production dependencies
RUN npm ci --omit=dev

# Expose Next.js default port
EXPOSE 3000

# Run the Next.js app
CMD ["npm", "start"]
