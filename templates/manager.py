"""
templates/manager.py - Project Templates Manager v7.1
List, apply, create, and delete project templates.
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


class TemplateManager:
    """Manage project templates."""
    
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Built-in templates
        self._builtin_templates = {
            "fastapi-crud": {
                "name": "FastAPI CRUD",
                "description": "Production-ready FastAPI CRUD application with SQLAlchemy",
                "stack": ["FastAPI", "SQLAlchemy", "PostgreSQL"],
                "files": ["models.py", "routes.py", "database.py", "schemas.py", "main.py", "requirements.txt", "README.md"],
            },
            "nextjs-dashboard": {
                "name": "Next.js Dashboard",
                "description": "Modern React dashboard with Next.js and Tailwind CSS",
                "stack": ["Next.js", "React", "Tailwind CSS"],
                "files": ["package.json", "pages/index.tsx", "components/Layout.tsx", "styles/globals.css", "README.md"],
            },
            "flutter-app": {
                "name": "Flutter App",
                "description": "Cross-platform mobile app with Flutter",
                "stack": ["Flutter", "Dart"],
                "files": ["pubspec.yaml", "lib/main.dart", "lib/screens/home.dart", "README.md"],
            },
            "react-spa": {
                "name": "React SPA",
                "description": "Single-page application with React and TypeScript",
                "stack": ["React", "TypeScript", "Vite"],
                "files": ["package.json", "src/App.tsx", "src/components/App.tsx", "README.md"],
            },
        }
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        templates = []
        
        # Add built-in templates
        for slug, info in self._builtin_templates.items():
            templates.append({
                "id": slug,
                "name": info["name"],
                "description": info["description"],
                "stack": info["stack"],
                "file_count": len(info["files"]),
                "builtin": True,
            })
        
        # Add custom templates
        for template_path in self.templates_dir.iterdir():
            if template_path.is_dir() and template_path.name not in self._builtin_templates:
                readme = template_path / "README.md"
                desc = readme.read_text()[:200] if readme.exists() else "Custom template"
                
                files = list(template_path.rglob("*"))
                py_files = [f for f in files if f.suffix == ".py"]
                
                templates.append({
                    "id": template_path.name,
                    "name": template_path.name.replace("-", " ").title(),
                    "description": desc,
                    "stack": ["custom"],
                    "file_count": len(files),
                    "builtin": False,
                })
        
        return templates
    
    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get details about a template."""
        if template_name in self._builtin_templates:
            info = self._builtin_templates[template_name]
            return {
                "id": template_name,
                **info,
                "builtin": True,
            }
        
        template_path = self.templates_dir / template_name
        if template_path.exists() and template_path.is_dir():
            readme = template_path / "README.md"
            desc = readme.read_text() if readme.exists() else "Custom template"
            
            files = []
            for f in template_path.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(template_path)
                    files.append(str(rel))
            
            return {
                "id": template_name,
                "name": template_name.replace("-", " ").title(),
                "description": desc[:200],
                "files": files,
                "builtin": False,
            }
        
        return None
    
    def preview_template(self, template_name: str) -> Dict[str, Any]:
        """Preview template file structure."""
        info = self.get_template_info(template_name)
        if not info:
            return {"error": "Template not found"}
        
        # Get file previews (first 20 lines of key files)
        previews = {}
        
        if template_name in self._builtin_templates:
            template_path = self.templates_dir / template_name
        else:
            template_path = self.templates_dir / template_name
        
        for py_file in ["main.py", "models.py", "routes.py"]:
            file_path = template_path / py_file
            if file_path.exists():
                lines = file_path.read_text().split("\n")[:20]
                previews[py_file] = "\n".join(lines) + "\n..."
        
        return {
            "template": info,
            "previews": previews,
        }
    
    def apply_template(
        self,
        template_name: str,
        project_path: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply template to create a new project.
        
        Returns files created.
        """
        if template_name not in self._builtin_templates:
            template_path = self.templates_dir / template_name
            if not template_path.exists():
                return {"error": f"Template '{template_name}' not found"}
        else:
            template_path = self.templates_dir / template_name
        
        dest_path = Path(project_path)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        copied_files = []
        
        # Copy all files from template
        for src_file in template_path.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(template_path)
                dest_file = dest_path / rel_path
                
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                copied_files.append(str(rel_path))
        
        # Create __init__.py if Python project
        py_files = list(dest_path.rglob("*.py"))
        if py_files and not (dest_path / "__init__.py").exists():
            (dest_path / "__init__.py").touch()
            copied_files.append("__init__.py")
        
        return {
            "success": True,
            "template": template_name,
            "project_path": str(dest_path),
            "files_created": len(copied_files),
            "files": copied_files,
        }
    
    def create_template_from_project(
        self,
        project_path: str,
        template_name: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """
        Save a project as a new template.
        """
        src_path = Path(project_path)
        if not src_path.exists():
            return {"error": "Project path not found"}
        
        template_path = self.templates_dir / template_name
        template_path.mkdir(parents=True, exist_ok=True)
        
        # Copy all files
        copied_files = []
        for src_file in src_path.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(src_path)
                dest_file = template_path / rel_path
                
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                copied_files.append(str(rel_path))
        
        # Create README if not exists
        readme = template_path / "README.md"
        if not readme.exists():
            readme.write_text(f"# {template_name}\n\n{description or 'Custom template'}\n")
            copied_files.append("README.md")
        
        return {
            "success": True,
            "template_name": template_name,
            "template_path": str(template_path),
            "files_copied": len(copied_files),
        }
    
    def delete_template(self, template_name: str) -> Dict[str, Any]:
        """Delete a custom template."""
        if template_name in self._builtin_templates:
            return {"error": "Cannot delete built-in templates"}
        
        template_path = self.templates_dir / template_name
        if not template_path.exists():
            return {"error": "Template not found"}
        
        shutil.rmtree(template_path)
        
        return {
            "success": True,
            "deleted": template_name,
        }


# Global instance
template_manager = TemplateManager()
