#!/bin/bash

# Tuma Core Deployment Script
# Run this script after pulling the repository onto your VPS
# Usage: bash deploy.sh

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths (adjust if needed)
PROJECT_ROOT="/root/projects/Tuma/TumiaCore"
VENV_NAME="tuma_env"
VENV_PATH="$PROJECT_ROOT/$VENV_NAME"
MANAGE_PY="$PROJECT_ROOT/manage.py"
PROJECT_DIR="$PROJECT_ROOT"
WSGI_MODULE="tuma_core.wsgi:application"

# Print colored message
print_message() {
    echo -e "${GREEN}[DEPLOY]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_step() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}========================================${NC}\n"
}

# Check if running as root or with sudo
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_error "This script requires sudo privileges for system configuration"
        print_info "Please run: sudo bash deploy.sh"
        exit 1
    fi
}

# Step 1: Create virtual environment
create_virtualenv() {
    print_step "Step 1: Creating Virtual Environment"
    
    cd "$PROJECT_ROOT" || exit 1
    
    if [ -d "$VENV_PATH" ]; then
        print_warning "Virtual environment already exists at $VENV_PATH"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_message "Removing old virtual environment..."
            rm -rf "$VENV_PATH"
        else
            print_message "Keeping existing virtual environment"
            return 0
        fi
    fi
    
    print_message "Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
    
    if [ -d "$VENV_PATH" ]; then
        print_message "✓ Virtual environment created successfully"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
}

# Step 2: Activate virtual environment (set variables for following commands)
setup_venv() {
    print_step "Step 2: Setting Up Virtual Environment"
    
    if [ ! -d "$VENV_PATH" ]; then
        print_error "Virtual environment not found at $VENV_PATH"
        exit 1
    fi
    
    print_message "Virtual environment ready at $VENV_PATH"
    print_info "Using Python: $VENV_PATH/bin/python"
    print_info "Using Pip: $VENV_PATH/bin/pip"
}

# Step 3: Install packages
install_packages() {
    print_step "Step 3: Installing Python Packages"
    
    cd "$PROJECT_ROOT" || exit 1
    
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt not found"
        exit 1
    fi
    
    print_message "Installing packages from requirements.txt..."
    "$VENV_PATH/bin/pip" install --upgrade pip
    "$VENV_PATH/bin/pip" install -r requirements.txt
    
    print_message "Installing gunicorn..."
    "$VENV_PATH/bin/pip" install gunicorn
    
    print_message "✓ All packages installed successfully"
}

# Step 4 & 5: Run migrations
run_migrations() {
    print_step "Steps 4 & 5: Running Database Migrations"
    
    cd "$PROJECT_DIR" || exit 1
    
    print_message "Creating migrations..."
    "$VENV_PATH/bin/python" manage.py makemigrations
    
    print_message "Applying migrations..."
    "$VENV_PATH/bin/python" manage.py migrate
    
    print_message "✓ Migrations completed successfully"
}

# Step 6: Create superuser
create_superuser() {
    print_step "Step 6: Creating Superuser"
    
    cd "$PROJECT_DIR" || exit 1
    
    print_info "You will now be prompted to enter superuser details"
    print_info "Press Ctrl+C to skip if superuser already exists"
    echo
    
    "$VENV_PATH/bin/python" manage.py createsuperuser || {
        print_warning "Superuser creation skipped or failed"
        print_info "You can create it later with: python manage.py createsuperuser"
    }
    
    echo
    print_message "Superuser setup complete"
}

# Step 7: Collect static files
collect_static() {
    print_step "Step 7: Collecting Static Files"
    
    cd "$PROJECT_DIR" || exit 1
    
    print_message "Collecting static files..."
    "$VENV_PATH/bin/python" manage.py collectstatic --noinput
    
    print_message "✓ Static files collected successfully"
}

# Step 8: Create systemd socket file
create_socket_file() {
    print_step "Step 8: Creating Systemd Socket File"
    
    SOCKET_FILE="/etc/systemd/system/tuma.socket"
    
    if [ -f "$SOCKET_FILE" ]; then
        print_warning "Socket file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_message "Keeping existing socket file"
            return 0
        fi
    fi
    
    print_message "Creating socket file at $SOCKET_FILE..."
    
    cat > "$SOCKET_FILE" << 'EOF'
[Unit]
Description=tuma socket

[Socket]
ListenStream=/run/tuma.sock

[Install]
WantedBy=sockets.target
EOF
    
    print_message "✓ Socket file created successfully"
}

# Step 9: Create systemd service file
create_service_file() {
    print_step "Step 9: Creating Systemd Service File"
    
    SERVICE_FILE="/etc/systemd/system/tuma.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        print_warning "Service file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_message "Keeping existing service file"
            return 0
        fi
    fi
    
    print_message "Creating service file at $SERVICE_FILE..."
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=gunicorn daemon for Tuma Core
Requires=tuma.socket
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_PATH/bin/gunicorn \\
          --access-logfile - \\
          --workers 3 \\
          --bind unix:/run/tuma.sock \\
          $WSGI_MODULE

[Install]
WantedBy=multi-user.target
EOF
    
    print_message "✓ Service file created successfully"
}

# Step 10 & 11: Start and enable socket
start_enable_socket() {
    print_step "Steps 10 & 11: Starting and Enabling Systemd Socket"
    
    print_message "Reloading systemd daemon..."
    systemctl daemon-reload
    
    print_message "Starting tuma socket..."
    systemctl start tuma.socket
    
    print_message "Enabling tuma socket..."
    systemctl enable tuma.socket
    
    print_message "✓ Socket started and enabled"
    
    # Check socket status
    print_info "Socket status:"
    systemctl status tuma.socket --no-pager || true
}

# Step 12: Configure Nginx
configure_nginx() {
    print_step "Step 12: Configuring Nginx"
    
    NGINX_CONFIG="/etc/nginx/sites-available/tuma_core"
    
    if [ -f "$NGINX_CONFIG" ]; then
        print_warning "Nginx configuration already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_message "Keeping existing Nginx configuration"
            return 0
        fi
    fi
    
    print_message "Creating Nginx configuration at $NGINX_CONFIG..."
    
    cat > "$NGINX_CONFIG" << 'EOF'
server {
    listen 80;
    server_name api.tuma.iolabz.ug;
    
    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
    }
    
    location /static/ {
        root /root/projects/Tuma/TumiaCore;
    }
    
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/tuma.sock;
    }
}
EOF
    
    print_message "✓ Nginx configuration created successfully"
}

# Step 13: Enable Nginx site
enable_nginx_site() {
    print_step "Step 13: Enabling Nginx Site"
    
    NGINX_AVAILABLE="/etc/nginx/sites-available/tuma_core"
    NGINX_ENABLED="/etc/nginx/sites-enabled/tuma_core"
    
    if [ -L "$NGINX_ENABLED" ]; then
        print_warning "Nginx site already enabled"
    else
        print_message "Creating symbolic link..."
        ln -s "$NGINX_AVAILABLE" "$NGINX_ENABLED"
        print_message "✓ Nginx site enabled"
    fi
    
    # Test Nginx configuration
    print_message "Testing Nginx configuration..."
    nginx -t || {
        print_error "Nginx configuration test failed"
        exit 1
    }
    
    print_message "✓ Nginx configuration is valid"
}

# Step 14: Restart Nginx
restart_nginx() {
    print_step "Step 14: Restarting Nginx"
    
    print_message "Restarting Nginx..."
    systemctl restart nginx
    
    print_message "✓ Nginx restarted successfully"
    
    # Check Nginx status
    print_info "Nginx status:"
    systemctl status nginx --no-pager || true
}

# Load fixtures (optional)
load_fixtures() {
    print_step "Optional: Loading Initial Data Fixtures"
    
    read -p "Do you want to load initial fixtures (modules, permissions)? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$PROJECT_DIR" || exit 1
        
        print_message "Loading modules fixture..."
        "$VENV_PATH/bin/python" manage.py loaddata modules || print_warning "Modules fixture not found or already loaded"
        
        print_message "Loading permissions fixture..."
        "$VENV_PATH/bin/python" manage.py loaddata permissions || print_warning "Permissions fixture not found or already loaded"
        
        print_message "✓ Fixtures loaded"
    else
        print_info "Skipping fixtures. You can load them later with:"
        print_info "  python manage.py loaddata modules permissions"
    fi
}

# Final status check
final_status() {
    print_step "Deployment Complete!"
    
    echo -e "${GREEN}✓ Virtual environment created${NC}"
    echo -e "${GREEN}✓ Packages installed${NC}"
    echo -e "${GREEN}✓ Database migrated${NC}"
    echo -e "${GREEN}✓ Superuser created${NC}"
    echo -e "${GREEN}✓ Static files collected${NC}"
    echo -e "${GREEN}✓ Systemd services configured${NC}"
    echo -e "${GREEN}✓ Nginx configured${NC}"
    
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}Next Steps:${NC}"
    echo -e "${BLUE}========================================${NC}\n"
    
    echo "1. Check service status:"
    echo "   sudo systemctl status tuma.socket"
    echo "   sudo systemctl status tuma.service"
    echo "   sudo systemctl status nginx"
    echo ""
    echo "2. View logs:"
    echo "   sudo journalctl -u tuma.service -f"
    echo ""
    echo "3. Test the API:"
    echo "   curl http://api.tuma.iolabz.ug/admin/"
    echo ""
    echo "4. Configure environment variables in .env file"
    echo ""
    echo "5. Set up SSL with Let's Encrypt:"
    echo "   sudo apt install certbot python3-certbot-nginx"
    echo "   sudo certbot --nginx -d api.tuma.iolabz.ug"
    echo ""
    echo -e "${GREEN}Your application should now be running!${NC}"
    echo -e "${GREEN}Admin: http://api.tuma.iolabz.ug/admin/${NC}"
    echo -e "${GREEN}API: http://api.tuma.iolabz.ug/api/${NC}"
}

# Main deployment flow
main() {
    print_message "Starting Tuma Core Deployment..."
    echo -e "${BLUE}Project Root: $PROJECT_ROOT${NC}"
    echo -e "${BLUE}Virtual Env: $VENV_PATH${NC}"
    echo -e "${BLUE}Project Dir: $PROJECT_DIR${NC}\n"
    
    # Confirm before proceeding
    read -p "Continue with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Deployment cancelled"
        exit 0
    fi
    
    # Check root
    check_root
    
    # Run all steps
    create_virtualenv
    setup_venv
    install_packages
    run_migrations
    create_superuser
    collect_static
    load_fixtures
    create_socket_file
    create_service_file
    start_enable_socket
    configure_nginx
    enable_nginx_site
    restart_nginx
    final_status
}

# Run main function
main

