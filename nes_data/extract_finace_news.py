import json
import os
import sys
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 保存为finance_news.jsonl文件

finance_news_list = []
# 财经、时政类新闻关键词
finance_political_keywords = ["股票", "基金", "期货", "汇率","美元","人民币","债券", "保险", "银行", "证券", "投行", "券商", "A股", "港股", "美股", "指数",
                              "行情", "涨跌", "涨幅", "跌幅", "开盘", "收盘", "央行","通胀", "通缩", "GDP", "CPI", "PPI", "利率", "准备金", "外汇", "贸易", "出口",
                              "进口", "关税", "税收", "赤字", "债务", "投资", "消费", "就业", "失业",
                              "欧元", "日元", "英镑", "美联储", "欧央行", "日央行", "加息", "降息", "量化", "宽松",
                              "紧缩", "泡沫", "崩盘", "救市", "IPO", "并购","重组", "退市", "停牌", "复牌", "蓝筹","题材", "概念", "板块",
                            "龙头", "国企", "民企", "外资", "合资", "上市", "退市", "融资",
                            "融券", "杠杆", "配资", "爆仓", "平仓", "止损", "止盈", "建仓", "加仓", "减仓","黄金","贵金属","油价"]

for i in range(18):
    # 文件名从00~19，如何处理文件名0的问题，需要在文件名前补0
    file_name = f"part-663de978334d-0000{i}.jsonl" if i >= 10 else f"part-663de978334d-00000{i}.jsonl"
    file_path = os.path.join("zh", file_name)
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                news = json.loads(line)
                # 检查新闻标题或内容是否包含财经、时政类关键词
                if any(keyword in news["title"] or keyword in news["content"] for keyword in finance_political_keywords):
                    # 再检查日期是否在2021年1月1日至2023年12月31日之间
                    if "2021" in news["date"] or "2022" in news["date"] or "2023" in news["date"]:
                        news['keywords'] = [keyword for keyword in finance_political_keywords if keyword in news["title"] or keyword in news["content"]]
                        # 只有当新闻包含至少2个关键词时才添加
                        if len(news['keywords']) >= 2:
                            finance_news_list.append(news)
                            print(f"已添加第{len(finance_news_list)}条财经新闻,id:{news['id']},关键词:{news['keywords']}")
    
# 保存提取后的财经新闻为JSONL文件
output_file = "D:\\workplace\\codeplace\\junkcode\\Qdt_test\\nes_data\\finance_news.jsonl"
with open(output_file, "w", encoding="utf-8") as f:
    for news in finance_news_list:
        json.dump(news, f, ensure_ascii=False)
        f.write("\n")

print(f"财经新闻提取完成，共保存 {len(finance_news_list)} 条新闻到 {output_file} 文件中。")