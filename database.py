
import json
import os
import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
TASKS_FILE = os.path.join(DATA_DIR, 'daily_logs.json')

# Default Initial Data if files don't exist
DEFAULT_USERS = {
    'admin': {
        'password': 'admin',
        'role': 'admin',
        'name': 'Martin',
        'avatar': '👨‍💻',
        'visible_modules': ['Toyota', 'Volkswagen', 'Others', 'e-CMR Manager', 'Vagoni', 'Statistika', 'Fakture', 'Produktivnost', 'Admin'],
        'dashboard_layout': ['kpi_stock', 'kpi_dispatched', 'kpi_loading', 'kpi_customs', 'flow_chart']
    },
    'martin.dumanic@blg.si': {
        'password': '666666',
        'role': 'admin',
        'name': 'Martin Dumanic',
        'avatar': 'M',
        'visible_modules': ['Toyota', 'Volkswagen', 'Others', 'e-CMR Manager'],
        'dashboard_layout': ['kpi_stock', 'kpi_dispatched']
    },
    'operativa': {
        'password': 'op',
        'role': 'operativa',
        'name': 'Operator',
        'avatar': '👷',
        'visible_modules': ['Toyota', 'Volkswagen'],
        'dashboard_layout': ['kpi_stock']
    },
    'service': {
        'password': 'srv',
        'role': 'service_admin',
        'name': 'ServiceAdmin',
        'avatar': '🔧',
        'visible_modules': ['Toyota'],
        'dashboard_layout': []
    }
}

class Database:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        if not os.path.exists(USERS_FILE):
            self.save_users(DEFAULT_USERS)
            
        if not os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def load_users(self):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")
            return {}

    def save_users(self, users_data):
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving users: {e}")
            return False

    def get_user(self, username):
        users = self.load_users()
        return users.get(username)

    def update_user_settings(self, username, settings_dict):
        """Allows partial updates to user profile/settings"""
        users = self.load_users()
        if username in users:
            users[username].update(settings_dict)
            self.save_users(users)
            return True
        return False
    
    def add_user(self, username, user_data):
        users = self.load_users()
        if username in users:
            return False # Already exists
        users[username] = user_data
        self.save_users(users)
        return True

    def delete_user(self, username):
        users = self.load_users()
        if username in users:
            del users[username]
            self.save_users(users)
            return True
        return False

    # --- Daily Tasks Logic ---
    def get_user_tasks(self, username, date_str):
        all_tasks = self._load_tasks()
        # Filter by username and date
        user_tasks = [t for t in all_tasks if t.get('username') == username and t.get('date') == date_str]
        return user_tasks

    def add_task(self, username, title, date_str, project_id=None):
        tasks = self._load_tasks()
        new_task = {
            'id': str(datetime.datetime.now().timestamp()), # Simple ID
            'username': username,
            'date': date_str,
            'title': title,
            'project_id': project_id,
            'completed': False,
            'timestamp': datetime.datetime.now().isoformat()
        }
        tasks.append(new_task)
        self._save_tasks(tasks)
        return new_task

    def update_task_status(self, task_id, completed):
        return self.update_task(task_id, {'completed': completed})

    def update_task(self, task_id, updates):
        tasks = self._load_tasks()
        for t in tasks:
            if t.get('id') == task_id:
                t.update(updates)
                self._save_tasks(tasks)
                return True
        return False

    def delete_task(self, task_id):
        tasks = self._load_tasks()
        initial_len = len(tasks)
        tasks = [t for t in tasks if t.get('id') != task_id]
        if len(tasks) < initial_len:
            self._save_tasks(tasks)
            return True
        return False
    
    def get_all_tasks_by_date(self, date_str):
        all_tasks = self._load_tasks()
        return [t for t in all_tasks if t.get('date') == date_str]

    def get_tasks_by_project(self, project_id):
        all_tasks = self._load_tasks()
        return [t for t in all_tasks if t.get('project_id') == project_id]

    def delete_task_by_project_and_user(self, project_id, username):
        tasks = self._load_tasks()
        initial_len = len(tasks)
        # Keep tasks that DO NOT match both project_id and username
        new_tasks = []
        for t in tasks:
            if t.get('project_id') == project_id and t.get('username') == username:
                continue
            new_tasks.append(t)
        
        if len(new_tasks) < initial_len:
            self._save_tasks(new_tasks)
            return True
        return False

    def _load_tasks(self):
        try:
            if not os.path.exists(TASKS_FILE):
                return []
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def _save_tasks(self, tasks):
        try:
            with open(TASKS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=4)
        except Exception as e:
            print(f"Error saving tasks: {e}")

    # --- Projects Logic ---
    def get_projects(self):
        return self._load_projects()

    def get_project(self, project_id):
        projects = self._load_projects()
        return next((p for p in projects if p['id'] == project_id), None)

    def save_project(self, project_data):
        projects = self._load_projects()
        # Check if update
        existing = next((i for i, p in enumerate(projects) if p['id'] == project_data['id']), None)
        if existing is not None:
            projects[existing] = project_data
        else:
            projects.append(project_data)
        self._save_projects(projects)
        return True

    def archive_project(self, project_id):
        projects = self._load_projects()
        for p in projects:
            if p['id'] == project_id:
                p['archived'] = True
                p['archived_at'] = datetime.datetime.now().isoformat()
                self._save_projects(projects)
                return True
        return False

    def delete_project(self, project_id):
        projects = self._load_projects()
        initial_len = len(projects)
        projects = [p for p in projects if p['id'] != project_id]
        if len(projects) < initial_len:
            self._save_projects(projects)
            return True
        return False
        
    def _load_projects(self):
        PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')
        try:
            if not os.path.exists(PROJECTS_FILE):
                return []
            with open(PROJECTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def _save_projects(self, projects):
        PROJECTS_FILE = os.path.join(DATA_DIR, 'projects.json')
        try:
            with open(PROJECTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(projects, f, indent=4)
        except Exception as e:
            print(f"Error saving projects: {e}")

db = Database()
