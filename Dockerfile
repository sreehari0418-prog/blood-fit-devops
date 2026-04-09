FROM nginx:alpine
# Copy static files to nginx public directory
COPY index.html /usr/share/nginx/html/
COPY style.css /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/
# Expose port 80
EXPOSE 80
