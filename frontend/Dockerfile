FROM nginx:alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy static assets (HTML, CSS, JS) from the build context
COPY . /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port from nginx.conf
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
