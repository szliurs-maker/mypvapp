import sys 
from streamlit.web import cli as stcli 
if __name__ == "__main__": 
    sys.argv = ["streamlit", "run", "C:\\Users\\Michael_Liu\\mypvapp\\app18.py", "--server.headless=false", "--global.developmentMode=false", "--server.enableStaticServing=true"] 
    sys.exit(stcli.main()) 
