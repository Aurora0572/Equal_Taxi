import pandas as pd

url = "http://m.calltaxi.sisul.or.kr/api/open/newEXCEL0001.asp?key=...&eDate=20250131"

df = pd.read_excel(url, engine='openpyxl')
print(df.head())
