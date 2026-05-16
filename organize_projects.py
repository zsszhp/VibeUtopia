import os
import re
import shutil
import subprocess

MD_PATH = "references/参考论文与开源项目.md"
PROJECTS_ROOT = "references/projects"

category_map = {
    "一、Agent 社会仿真与社交网络模拟": "01_Agent_Simulation",
    "二、舆论极化、回音室与信息传播": "02_Opinion_Dynamics",
    "三、Agent 记忆系统与人格建模": "03_Agent_Memory",
    "四、内容理解与多模态分析": "04_Multimodal_Analysis",
    "五、内容风控与安全": "05_Safety_and_Risk",
    "六、知识图谱与 GraphRAG": "06_GraphRAG",
    "七、LLM 工程与 Agent 框架": "07_LLM_Engineering",
    "八、你已收集的参考项目（确认与补充）": "08_Existing_Projects"
}

os.makedirs(PROJECTS_ROOT, exist_ok=True)

# 1. Parse markdown to get category -> [project_urls]
category_to_urls = {}
current_cat = None

with open(MD_PATH, "r", encoding="utf-8") as f:
    for line in f:
        m = re.match(r'##\s+(.*)', line.strip())
        if m:
            cat_name = m.group(1).strip()
            if cat_name in category_map:
                current_cat = category_map[cat_name]
                if current_cat not in category_to_urls:
                    category_to_urls[current_cat] = []
            continue
        
        if current_cat:
            # Look for github links
            urls = re.findall(r'https://github\.com/([\w\-]+/[\w\-]+)', line)
            for url in urls:
                full_url = f"https://github.com/{url}.git"
                if full_url not in category_to_urls[current_cat]:
                    category_to_urls[current_cat].append(full_url)

# 2. Download/Clone missing projects and move them to category folders
for cat_folder, urls in category_to_urls.items():
    cat_path = os.path.join(PROJECTS_ROOT, cat_folder)
    os.makedirs(cat_path, exist_ok=True)
    
    for url in urls:
        repo_name = url.split('/')[-1].replace('.git', '')
        dest_path = os.path.join(cat_path, repo_name)
        
        if not os.path.exists(dest_path):
            print(f"Cloning {repo_name} into {cat_folder}...")
            try:
                # Clone into temporary location first if it already exists somewhere else
                # Actually, check if it's already in PROJECTS_ROOT
                found = False
                for root, dirs, files in os.walk(PROJECTS_ROOT):
                    if repo_name in dirs:
                        existing_path = os.path.join(root, repo_name)
                        if existing_path != dest_path:
                            print(f"Moving existing project {repo_name} to {dest_path}")
                            shutil.move(existing_path, dest_path)
                            found = True
                            break
                
                if not found:
                    subprocess.run(["git", "clone", "--depth", "1", url, dest_path], check=True)
            except Exception as e:
                print(f"Error handling {repo_name}: {e}")
        else:
            print(f"Project {repo_name} already exists in {cat_folder}.")

# 3. Clean up empty or redundant folders in PROJECTS_ROOT
for entry in os.scandir(PROJECTS_ROOT):
    if entry.is_dir() and entry.name not in category_map.values():
        # Check if it's empty
        try:
            if not os.listdir(entry.path):
                print(f"Removing empty directory: {entry.name}")
                os.rmdir(entry.path)
            else:
                # If it's not a category folder, it might be a misplaced project
                # We already tried to move them in step 2. If it's still here, maybe it's unknown.
                print(f"Misplaced directory remaining: {entry.name}")
                # Optional: shutil.rmtree(entry.path) if you are sure
        except Exception as e:
            print(f"Error cleaning {entry.name}: {e}")

print("Project organization complete.")
