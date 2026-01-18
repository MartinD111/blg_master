import sys
import os
import datetime
import json

# Add current directory to path
sys.path.append(os.getcwd())

from app import app, db, sync_project_to_tasks

def test_sync():
    print("Starting Sync Verification...")
    
    # Setup Context
    with app.app_context():
        # 1. Create a Test Project via DB directly (simulating API payload)
        project_id = "test_sync_proj_1"
        username = "admin"
        
        project = {
            'id': project_id,
            'title': "Sync Test Project",
            'description': "Testing sync",
            'status': "todo",
            'assignees': [username],
            'created_by': "admin",
            'created_at': datetime.datetime.now().isoformat(),
            'archived': False
        }
        
        print(f"1. Creating Project: {project['title']} assigned to {username}")
        db.save_project(project)
        sync_project_to_tasks(project)
        
        # Verify Task Created
        tasks = db.get_tasks_by_project(project_id)
        user_tasks = [t for t in tasks if t['username'] == username]
        
        if not user_tasks:
            print("FAIL: Task not created for assignee.")
            return
        
        task = user_tasks[0]
        print(f"PASS: Task created: {task['title']} (ID: {task['id']})")
        
        if task['title'] != "[Project] Sync Test Project":
             print(f"FAIL: Task title mismatch. Got {task['title']}")
        
        # 2. Update Project Status to DONE
        print("2. Updating Project Status to DONE")
        project['status'] = 'done'
        db.save_project(project)
        sync_project_to_tasks(project)
        
        # Verify Task Completed
        task_updated = [t for t in db.get_tasks_by_project(project_id) if t['id'] == task['id']][0]
        if task_updated['completed']:
            print("PASS: Task marked as completed.")
        else:
             print("FAIL: Task NOT marked as completed.")

        # 3. Update Project Title
        print("3. Updating Project Title")
        project['title'] = "Renamed Project"
        db.save_project(project)
        sync_project_to_tasks(project)
        
        # Verify Task Renamed
        task_renamed = [t for t in db.get_tasks_by_project(project_id) if t['id'] == task['id']][0]
        if task_renamed['title'] == "[Project] Renamed Project":
            print("PASS: Task title updated.")
        else:
            print(f"FAIL: Task title NOT updated. Got {task_renamed['title']}")

        # 4. Unassign User
        print("4. Unassigning User")
        project['assignees'] = []
        db.save_project(project)
        sync_project_to_tasks(project)
        
        # Verify Task Deleted
        tasks_final = db.get_tasks_by_project(project_id)
        if not tasks_final:
            print("PASS: Task deleted after unassign.")
        else:
            print(f"FAIL: Task still exists: {tasks_final}")

        # Cleanup Project
        db.delete_project(project_id)
        print("Cleanup done.")

if __name__ == "__main__":
    test_sync()
