# Configuring IntelliJ for Python CDK Development

## Status
✅ Virtual environment created and configured at:
```
/Users/mhodges/university-of-hawaii-system-its-iam/example-aws-IaC/infra/.venv
```

✅ AWS CDK and dependencies installed.

## Configure IntelliJ to Use the Virtual Environment

### Step 1: Open Project Settings
1. In IntelliJ, go to **IntelliJ IDEA → Preferences** (or **File → Settings** on Linux/Windows)
2. Navigate to **Project: example-aws-IaC → Python Interpreter**

### Step 2: Add the Virtual Environment
1. Click the gear icon ⚙️ and select **Add...**
2. Select **Existing Environment**
3. Click the **...** button to browse
4. Navigate to and select:
   ```
   /Users/mhodges/university-of-hawaii-system-its-iam/example-aws-IaC/infra/.venv/bin/python
   ```
5. Click **OK** to add the interpreter

### Step 3: Set as Project Interpreter
1. In the Python Interpreter dropdown, select the virtual environment you just added
2. Click **Apply** then **OK**

### Step 4: Mark the `infra` Folder as Sources Root (Optional but Recommended)
1. Right-click on the `infra` folder in the project tree
2. Select **Mark Directory as → Sources Root**
3. This helps IntelliJ resolve imports correctly

## Verify the Configuration

After configuring IntelliJ, the red squiggly lines under `aws_cdk` imports should disappear within seconds. 

If they don't:
1. **Invalidate Caches** → Go to **File → Invalidate Caches → Invalidate and Restart**
2. Wait for IntelliJ to restart and reindex the project

## Run/Deploy from IntelliJ

Once configured, you can:

### Synthesize the CDK
```bash
cdk synth LogArchivalStack
```

### Deploy a Stack
```bash
cdk deploy LogArchivalStack
```

### View Generated CloudFormation
Check `cdk.out/` directory after running `cdk synth`

## Virtual Environment Details

- **Location:** `/Users/mhodges/university-of-hawaii-system-its-iam/example-aws-IaC/infra/.venv`
- **Python Version:** 3.11
- **Installed Packages:**
  - `aws-cdk-lib>=2.100.0`
  - `constructs>=10.0.0`

## Activate Virtual Environment in Terminal

If you need to manually activate the venv in a terminal:

```bash
cd /Users/mhodges/university-of-hawaii-system-its-iam/example-aws-IaC/infra
source .venv/bin/activate
```

You'll see `(.venv)` prefix in your prompt when active.

To deactivate:
```bash
deactivate
```

---

**After completing these steps, all IntelliJ IDE errors should be resolved!**

