import os
import json

news_data_dir = r'D:\workplace\codeplace\junkcode\Qdt_test\nes_data'
news_data = []
file_path = os.path.join(news_data_dir, f'finance_news_tagged_10.jsonl')
with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        news_data.append(data)
#"date": "2022-05-27"
# 按照每一项的"date"进行排序
news_data.sort(key=lambda x: x['date'])
# 然后统一写回一个jsonl文件
with open(os.path.join(news_data_dir, 'finance_news_tagged.jsonl'), 'w', encoding='utf-8') as f:
    for i, data in enumerate(news_data):
        print(f"正在写入第{i}条数据，日期为：{data['date']}......")
        f.write(json.dumps(data, ensure_ascii=False) + '\n')
