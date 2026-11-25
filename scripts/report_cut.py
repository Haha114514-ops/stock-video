# -*- coding: utf-8 -*-
"""定期报告 PDF → 带页标记的全文 + 管理层讨论 + 按清单切好的段 + 目录索引（57号补丁十一）。
切段：主要会计数据、分季度、审计报告关键审计事项、利润分配、管理层讨论、二十来条附注；
只给页码：三张合并报表、重大诉讼、重大关联交易、担保。
材料员先读 <标题>_目录索引.md 和切好的段；清单外的内容用关键词在 _全文.txt 里定位，只读命中的那几页，不通读全文。

用法：python report_cut.py <PDF> [<输出目录>] [--title=标题] [--notes=关键词1,关键词2]
  输出目录  默认 PDF 所在目录
  --title   输出文件名前缀，默认 PDF 文件名
  --notes   清单外要切的附注科目（这期命门相关，如 商誉,开发支出），按"编号. 科目名"标题找
产出（都在输出目录）：
  <标题>_全文.txt            每页前一行 =====PDF第N页=====，抄出处时用这个页码
  <标题>_管理层讨论与分析.txt
  <标题>_附注_<名>.txt       清单里每一项一份，文件头写页码范围；超过 CAP 字截断并在索引里标出
  <标题>_目录索引.md         各节起始页、切好的段（页码 / 字数）、清单里没切到的项
fetch_data.py 下载年报 / 半年报后自动调用；季报、港股 PDF 可手动跑。
港股年报 / 中期报告（香港财务报告准则；繁体或简体、「綜合」或「合併」、中英双语都认）自动认出、走另一套：按每页前几行的标题
（去掉公司名、报告名这类重复页眉）切管理层讨论与分析、关键审计事项、四张主表，附注按递增编号切清单里的科目
（所得税、租赁、贸易应付、合约负债、物业减值、股息 / 储备等），索引另列附注编号一览；双语报告切好的段只留中文行。
A 股一季报 / 三季报（没有附注）按"一、/（一）"标题和三张合并报表切。"""
import bisect, io, os, re, sys

PAGE = '=====PDF第{}页====='
PAGE_RE = re.compile(r'^=====PDF第(\d+)页=====$', re.M)
CN = '一二三四五六七八九十'
NL = r'[ \t]*(?:\n[ \t]*)?'   # 编号和标题之间可以换行（"六、" 单独一行，招商蛇口 2026 半年报）
CAP = 20000

# ---------- 清单 ----------
# 编号附注（"合并财务报表项目注释"一节里，"33." 换行 "长期借款"，或 "33、长期借款"）：名 → 科目名正则
NUM_NOTES = {
    '营业收入和营业成本': r'营业收入[和及、]营业成本|营业收入、营业成本',
    '所得税费用': r'所得税费用',
    '财务费用': r'财务费用',
    '投资收益': r'投资收益',
    '资产减值损失': r'资产减值损失',
    '信用减值损失': r'信用减值损失',
    '公允价值变动收益': r'公允价值变动(收益|损益)',
    '货币资金': r'货币资金',
    '应收账款': r'应收账款',
    '存货': r'存货',
    '商誉': r'商誉',
    '合同负债': r'合同负债',
    '短期借款': r'短期借款',
    '一年内到期的非流动负债': r'(一|1)[ \t]*年内到期的非流动负债',   # 金隅写"1 年内"
    '长期借款': r'长期借款',
    '应付债券': r'应付债券',
    '租赁负债': r'租赁负债',
    '现金流量表补充资料': r'现金流量表补充资料',
    '分部信息': r'分部(信息|报告)',
}
# 一级标题（"十二、资产负债表日后事项"）：名 → 标题正则；在整份报告里找
TOP_NOTES = {
    '主要会计数据': r'(近三年)?(公司)?主要会计数据(和财务指标)?',
    '分季度数据': r'(\d{4}[ \t]*年)?分季度主要财务(指标|数据)',
    '关键审计事项': r'关键审计事项[：:]?',
    '利润分配': r'(公司)?(本报告期)?利润分配(及资本公积金转增股本(情况|预案)|或资本公积金转增预案)',
    '非经常性损益': r'非经常性损益项目及金额|非经常性损益项目和金额',
    '资产负债表日后事项': r'资产负债表日后事项',
    '承诺及或有事项': r'承诺及或有事项|或有事项',
    '合并范围变更': r'合并范围的变(更|动)',   # 紫金写"变动"；"七、合并范围的变动 - 续"这类页眉不算结束
}
# 并表信息：目录里也有同名标题，取最长的一段（沿用 fetch_data 原逻辑）
SPAN_NOTES = {
    '子公司权益': (r'在子公司中的权益', r'在合营(企业|安排)[和或及]联营企业中的权益'),
}
KEEP_NAME = {'子公司权益', '合并范围变更'}   # 沿用旧文件名 <标题>_子公司权益.txt，不加"附注_"
# 只给页码、不切段（原表和"重要事项"各条写法差别大，到全文里读那几页）：名 → 单独成行的标题
LANDMARKS = {
    '合并资产负债表': r'(\d[、.．][ \t]*)?合并资产负债表',
    '合并利润表': r'(\d[、.．][ \t]*)?合并利润表',
    '合并现金流量表': r'(\d[、.．][ \t]*)?合并现金流量表',
    '重大诉讼、仲裁': rf'([{CN}]+、[ \t]*)?重大诉讼、仲裁事项',
    '重大关联交易': rf'([{CN}]+、[ \t]*)?重大关联交易',
    '担保': r'(\d[、.．][ \t]*)?重大担保|[（(]二[)）][ \t]*担保情况|担保情况',
}

# ---------- 抽文本 ----------
def pdf_text(pdf):
    import fitz
    with fitz.open(pdf) as doc:
        return '\n'.join(PAGE.format(i + 1) + '\n' + pg.get_text() for i, pg in enumerate(doc))

class Pages:
    def __init__(self, text):
        self.pos = [m.start() for m in PAGE_RE.finditer(text)]
        self.no = [int(m.group(1)) for m in PAGE_RE.finditer(text)]
    def at(self, p):
        i = bisect.bisect_right(self.pos, p) - 1
        return self.no[i] if i >= 0 else 1
    def span(self, a, b):
        a, b = self.at(a), self.at(max(a, b - 1))
        return f'第 {a} 页' if a == b else f'第 {a}~{b} 页'

# ---------- 管理层讨论与分析 ----------
# 只认行首：正文里"详见本报告'第五节重要事项…'"这类交叉引用不算下一节（招商蛇口 2025 年报因此只切到第 46 页，实际到第 61 页）。
# "第X节"后允许换行（金隅："第五节"单独一行，"重要事项"在下一行）
HEAD = re.compile(r'^[ \t]*第[一二三四五六七八九十]+[节章]\s*\S', re.M)
MDA = re.compile(r'^[ \t]*第[一二三四五六七八九十]+[节章]\s*(管理层讨论与分析|经营情况讨论与分析|董事会报告)', re.M)
# 正文标题不带"第X节"的版式（紫金矿业 2025 年报、2026 半年报：只有目录带"第三节"，正文标题是单独一行）
MDA_LINE = re.compile(r'^[ \t]*(管理层讨论与分析|经营情况讨论与分析)[ \t]*$', re.M)
END_LINE = re.compile(r'^[ \t]*(公司治理|重要事项|环境与社会责任|环境与应对气候改变|股份变动及股东情况)[ \t]*$', re.M)

def extract_mda(text):
    """正文里的"管理层讨论与分析"一节：目录里也会出现同名标题，取到下一节之间最长的那一段。
    按"第X节"取不到（<2000 字）时，退回按单独成行的标题取，到下一个单独成行的节名为止。返回 (起, 止)。"""
    best = (0, 0)
    for m in MDA.finditer(text):
        nxt = HEAD.search(text, m.end() + 20)
        e = nxt.start() if nxt else len(text)
        if e - m.start() > best[1] - best[0]: best = (m.start(), e)
    if best[1] - best[0] < 2000:
        for m in MDA_LINE.finditer(text):
            e = END_LINE.search(text, m.end() + 20)
            e = min(e.start() if e else len(text), m.start() + 150000)
            if e - m.start() > best[1] - best[0]: best = (m.start(), e)
    return best

# ---------- 附注 ----------
def notes_region(text):
    """"合并财务报表项目注释"一节到"母公司财务报表…注释"为止；分部、期后事项在中间也算。找不到就返回 None。"""
    st = re.search(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}合并财务报表(主要)?项目(注释|附注)[ \t]*$', text, re.M)
    if not st: return None
    en = re.search(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}(母公司|公司)财务报表(主要)?项目(注释|附注)', text[st.end():], re.M)
    return st.start(), st.end() + en.start() if en else len(text)

def num_head(kw, n=None):
    num = str(n) if n else r'\d{1,3}'
    # 标题后可带"（续）""/ (净收益)"之类的尾巴（华润三九"54、财务费用 / (净收益)"）
    return re.compile(rf'^[ \t]*({num})[ \t]*[、.．]{NL}(?:{kw})[ \t]*(?:[/／][ \t]*)?(?:[（(][^\n]{{0,30}}[)）])?[ \t]*$', re.M)

def cut_num(text, region, kw):
    a, b = region
    for m in num_head(kw).finditer(text, a, b):
        n = int(m.group(1))
        nxt = re.compile(rf'^[ \t]*{n + 1}[ \t]*[、.．][ \t]*(?:\n[ \t]*)?[一-鿿]', re.M).search(text, m.end(), b)
        e = nxt.start() if nxt else min(b, m.end() + CAP)
        if e - m.start() >= 100: return m.start(), e
    return None

TOP_ANY = re.compile(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}[一-鿿][^\n]*$', re.M)

def cut_top(text, kw, pg):
    """先找带"十二、"编号的标题，到下一个一级标题为止；一处都没有，再找单独成行、不带编号的
    （紫金"非经常性损益项目和金额"），认不出结尾，就取到标题所在页的下一页末。返回 (起, 止, 是否无编号)。"""
    best = None
    for m in re.finditer(rf'^[ \t]*[{CN}]+[ \t]*[、.．]{NL}(?:{kw})[ \t]*$', text, re.M):
        e = len(text)
        for n in TOP_ANY.finditer(text, m.end() + 20):
            if '续' not in n.group(0): e = n.start(); break
        e = min(e, m.start() + CAP * 2)
        if e - m.start() >= 100 and (best is None or e - m.start() > best[1] - best[0]): best = (m.start(), e)
    if best: return (*best, False)
    for m in re.finditer(rf'^[ \t]*(?:{kw})[ \t]*$', text, re.M):
        nxt = PAGE_RE.search(text, text.find(PAGE.format(pg.at(m.start()) + 1)) + 1) if PAGE.format(pg.at(m.start()) + 1) in text else None
        e = nxt.start() if nxt else len(text)
        if e - m.start() >= 100: return m.start(), e, True
    return None

def cut_span(text, st, en):
    best = None
    for m in re.finditer(st, text):
        e = re.search(en, text[m.end() + 20:])
        e = m.end() + 20 + e.start() if e else m.start() + 40000
        e = min(e, m.start() + 40000)
        if best is None or e - m.start() > best[1] - best[0]: best = (m.start(), e)
    return best

# ---------- 港股（繁体或简体、香港财务报告准则）----------
# 港股年报 / 中期报告没有"第X节""合并资产负债表""一、合并财务报表项目注释"，A 股这套一段都切不到。港股版式的几种变体都要认：
#   繁体为主 / 简体为主夹繁体字；主表叫「綜合」或「合併」，资产负债表叫「財務狀況表」「財務狀況報表」或「資產負債表」，中期报告前面多「簡明」；
#   页首可能是 公司名 / 报告名 单双页交替（各占一半页数），也可能是笼统的「財務報表」，真正的栏目名在下面几行；
#   中英双语排版（同一页英文段 + 中文段）。
# 做法：先繁→简逐字转换再匹配（一对一，位置不变，切出来的仍是原文）；每页取前 12 行里去掉"重复页眉"（多页都有、又不是栏目名的行）
# 和页码后的短行当标题候选；同一页命中 3 个以上栏目的是目录页，不算。附注标题是"编号单独一行（或同一行）+ 科目名"，只认从 1 递增的编号。
_T2S_PAIRS = (
    '萬万與与專专業业叢丛東东絲丝兩两嚴严喪丧個个豐丰臨临為为爲为麗丽舉举義义烏乌樂乐喬乔習习鄉乡書书買买亂乱爭争於于虧亏雲云亞亚產产'
    '畝亩親亲億亿僅仅從从侖仑倉仓儀仪們们價价眾众衆众優优夥伙會会傘伞偉伟傳传傷伤倫伦偽伪體体餘余傭佣僱雇俠侠侶侣偵侦側侧僑侨儉俭債债'
    '傾倾償偿儲储兒儿兌兑黨党蘭兰關关興兴茲兹養养獸兽內内岡冈冊册寫写軍军農农馮冯衝冲沖冲決决況况凍冻淨净涼凉減减湊凑幾几鳳凤憑凭凱凯'
    '擊击鑿凿劃划劉刘則则剛刚創创刪删別别劑剂剮剐劍剑劇剧勸劝辦办務务動动勵励勁劲勞劳勢势勳勋勻匀匯汇滙汇彙汇區区醫医華华協协單单賣卖'
    '盧卢滷卤衛卫卻却廠厂廳厅曆历歷历厲厉壓压厭厌廁厕廂厢廈厦廚厨縣县參参雙双發发髮发變变敘叙疊叠葉叶號号嘆叹籲吁後后嚇吓呂吕嗎吗噸吨'
    '聽听啟启吳吴員员詠咏嚨咙響响啞哑嘩哗喚唤嘖啧嗇啬噴喷噓嘘囂嚣團团糰团園园圍围國国圖图圓圆聖圣場场壞坏塊块堅坚壇坛壩坝墳坟墜坠壟垄'
    '壘垒墾垦墊垫塹堑墮堕牆墙壯壮聲声殼壳壺壶處处備备複复復复夠够頭头誇夸夾夹奪夺奮奋獎奖奧奥妝妆婦妇媽妈婁娄嬌娇娛娱嬰婴孫孙學学寧宁'
    '寶宝實实寵宠審审憲宪宮宫寬宽賓宾寢寝對对尋寻導导壽寿將将爾尔塵尘嘗尝嚐尝堯尧屍尸盡尽儘尽層层屆届屬属屢屡嶼屿歲岁豈岂嶇岖崗岗島岛'
    '嶺岭峽峡巒峦嶄崭巔巅鞏巩幣币帥帅師师帳账賬账簾帘幟帜帶带幀帧幫帮莊庄慶庆廬庐龐庞廢废廟庙庫库應应開开異异棄弃張张彌弥彎弯彈弹強强'
    '歸归當当噹当錄录彥彦徹彻徑径憶忆懷怀態态憐怜總总戀恋懇恳惡恶噁恶惱恼悅悦懸悬驚惊懼惧慘惨懲惩慚惭慣惯憤愤願愿懶懒戲戏戰战戶户紮扎'
    '撲扑託托執执擴扩掃扫揚扬擾扰撫抚搶抢護护報报擔担擬拟攏拢揀拣擁拥攔拦擰拧撥拨擇择掛挂摯挚挾挟擋挡掙挣擠挤揮挥撈捞損损撿捡換换搗捣'
    '據据擄掳擲掷摻掺攬揽擱搁摟搂攪搅攜携攝摄擺摆搖摇攤摊撐撑攢攒敵敌斂敛數数齋斋鬥斗斬斩斷断無无舊旧時时曠旷晝昼顯显晉晋曬晒曉晓暈晕'
    '暉晖暫暂術术樸朴機机殺杀雜杂權权條条來来楊杨傑杰極极構构樞枢棗枣槍枪楓枫檸柠欄栏樹树棲栖樣样楨桢檔档橋桥樺桦樁桩夢梦檢检槓杠樓楼'
    '欖榄櫚榈檻槛檳槟橫横櫻樱櫥橱櫃柜歡欢歐欧殲歼殘残殯殡毆殴毀毁畢毕斃毙氈毡氣气氫氢漢汉湯汤洶汹溝沟沒没瀝沥淪沦滄沧滬沪濘泞淚泪瀘泸'
    '瀉泻潑泼澤泽涇泾潔洁灑洒窪洼淺浅漿浆澆浇濁浊測测濟济瀏浏渾浑濃浓濤涛澇涝漣涟渦涡滌涤潤润澗涧漲涨澀涩澱淀淵渊漬渍瀆渎漸渐漁渔瀋沈'
    '滲渗溫温遊游灣湾濕湿潰溃濺溅滎荥滅灭燈灯靈灵災灾燦灿爐炉燉炖點点煉炼熾炽爍烁爛烂烴烃燭烛煙烟煩烦燒烧燴烩燙烫燼烬熱热煥焕愛爱爺爷'
    '牘牍犧牺犢犊狀状猶犹狽狈猙狰獨独狹狭獅狮獄狱獰狞獵猎豬猪貓猫獻献瑪玛瑋玮環环現现璽玺瓏珑瑣琐瓊琼瑤瑶電电畫画暢畅疇畴療疗瘧疟瘡疮'
    '瘋疯癢痒癱瘫癮瘾皺皱盞盏鹽盐監监蓋盖盜盗盤盘睜睁瞞瞒矯矫礦矿碼码磚砖硯砚礎础碩硕確确鹼碱礙碍禮礼禍祸稟禀祿禄禪禅離离禿秃稈秆種种'
    '積积稱称穢秽穩稳穀谷窮穷竊窃竅窍窯窑竄窜窩窝窺窥竇窦豎竖競竞筆笔筍笋箋笺籠笼篤笃篩筛箏筝籌筹簽签籤签簡简籃篮籬篱類类糞粪糧粮緊紧'
    '糾纠紀纪約约紅红纖纤紋纹納纳紐纽紓纾純纯紗纱綸纶紛纷紙纸級级紜纭紡纺細细練练組组紳绅紹绍終终經经綁绑絨绒結结繞绕給给絢绚絡络絕绝'
    '絞绞統统絹绢繡绣綢绸綜综綻绽綠绿綴缀緒绪綾绫續续綺绮緋绯綽绰繩绳維维綿绵綬绶繃绷縷缕編编緣缘緩缓締缔緬缅緯纬緞缎線线綫线緝缉縛缚'
    '縫缝縮缩縱纵繆缪纓缨繕缮織织繚缭繽缤繹绎繼继纏缠纜缆繳缴網网羅罗罰罚罷罢羈羁羨羡翹翘聶聂聾聋職职聯联聰聪肅肃腸肠膚肤腎肾腫肿脹胀'
    '脅胁膽胆勝胜朧胧脛胫膠胶脈脉臍脐腦脑膿脓腳脚脫脱臉脸臘腊膩腻騰腾臟脏髒脏艦舰艙舱艱艰艷艳藝艺節节蕪芜蘆芦葦苇蒼苍蘋苹莖茎薦荐蕎荞'
    '薈荟蕩荡盪荡榮荣葷荤熒荧蔭荫藥药蓮莲獲获穫获瑩莹鶯莺蘿萝螢萤營营縈萦蕭萧薩萨蔥葱蔣蒋藍蓝薊蓟蘊蕴薔蔷蘚藓蘇苏虜虏慮虑雖虽蝦虾蝕蚀'
    '蟻蚁螞蚂蠶蚕蠻蛮蟄蛰蛻蜕蝸蜗蠟蜡蠅蝇蟬蝉釁衅銜衔補补襯衬襖袄襪袜襲袭裝装褲裤見见觀观規规覓觅視视覽览覺觉觸触訂订計计訊讯討讨訓训'
    '記记訛讹訝讶訟讼訣诀訪访設设許许訴诉診诊註注詐诈詔诏評评詞词詢询試试詩诗詫诧詭诡詮诠詰诘話话該该詳详誅诛誌志認认誕诞誘诱語语誠诚'
    '誡诫誣诬誤误誦诵誨诲說说誰谁課课誹诽誼谊調调諂谄談谈請请諒谅論论諜谍諧谐諫谏諭谕諮咨諱讳諷讽諸诸諾诺謀谋謁谒謂谓謊谎謎谜謙谦講讲'
    '謝谢謠谣謬谬謹谨證证譏讥識识譜谱譯译議议譴谴譽誉讀读讓让讚赞貝贝貞贞負负貢贡財财責责賢贤敗败貨货質质販贩貪贪貧贫貶贬購购貯贮貫贯'
    '貳贰賤贱貼贴貴贵貸贷貿贸費费賀贺賊贼賈贾賄贿賃赁賂赂資资賑赈賒赊賦赋賭赌贖赎賞赏賜赐賠赔賴赖贅赘賽赛贈赠贊赞贍赡贏赢贓赃趙赵趕赶'
    '趨趋躍跃踐践蹤踪軀躯車车軋轧軌轨軒轩轉转輪轮軟软轟轰軸轴輕轻載载轎轿輔辅輛辆輩辈輝辉輸输輻辐輯辑輾辗轄辖轍辙辭辞辯辩邊边遼辽達达'
    '遷迁過过邁迈運运還还這这進进遠远違违連连遲迟適适選选遜逊遞递邏逻遺遗鄧邓郵邮鄒邹鄰邻鄭郑醞酝醬酱釀酿釋释裏里裡里鑒鉴鑑鉴針针釘钉'
    '釣钓鈣钙鈍钝鈔钞鈞钧鈕钮鈦钛鈴铃鉀钾鉅巨鉛铅鉑铂鉤钩銀银銅铜銘铭銳锐銷销鋁铝鋅锌鋒锋鋼钢錢钱錦锦錫锡錯错鍋锅鍍镀鍵键鍾钟鐘钟鎊镑'
    '鎖锁鎮镇鏈链鏡镜鐵铁鑄铸鑰钥鑽钻長长門门閃闪閉闭問问闖闯閏闰閑闲閒闲間间悶闷閘闸鬧闹閨闺聞闻閩闽閣阁閥阀閱阅閻阎闊阔闆板闡阐闢辟'
    '隊队階阶際际陸陆陳陈陰阴陽阳隕陨險险隨随隱隐隴陇隸隶隻只雋隽難难雛雏雞鸡霧雾靂雳靄霭靜静韋韦韌韧韓韩韻韵頁页頂顶頃顷項项順顺須须'
    '頑顽顧顾頓顿頒颁頌颂預预領领頗颇頸颈頰颊頻频頤颐頹颓額额顏颜題题顛颠類类顯显顫颤風风颱台颳刮飄飘飛飞飯饭飲饮飼饲飽饱飾饰餃饺餅饼'
    '餌饵館馆餵喂饑饥饒饶馬马馭驭馳驰駁驳駐驻駕驾駛驶駭骇騎骑驗验驅驱驟骤髏髅鬆松鬍胡鬚须魚鱼魯鲁鮮鲜鯨鲸鳥鸟鳴鸣鴻鸿鵝鹅鶴鹤鷹鹰鹵卤'
    '鹹咸麥麦黃黄黴霉齊齐齒齿齡龄龍龙龜龟併并並并準准週周製制佔占徵征癥症佈布佈布臺台檯台麼么嶽岳蹟迹跡迹傢家蒐搜鬱郁嚮向麵面範范'
    '釐厘劵券擱搁攙搀託托誌志閤合絃弦峯峰儅当瞭了稅税採采標标績绩衞卫祕秘彿佛盃杯纍累'
)
T2S = str.maketrans({a: b for a, b in zip(_T2S_PAIRS[::2], _T2S_PAIRS[1::2]) if a != b})
def norm(s): return s.translate(T2S)
_X = r'(?:[（(][^)）\n]{0,12}[)）])?'           # 标题尾巴：（未經審核）（續）之类
_PFX = r'(?:简明)?(?:中期)?(?:简明)?(?:综合|合并)?'
HK_PART = {   # 栏目 → 标题行正则（简体，整行匹配，标题行先去掉"（续）"）
    '管理层讨论与分析': r'(?:[^\n]{0,8})?管理层(?:讨论|论述)(?:与|及|和)分析[^\n]{0,8}|业务回顾(?:及展望)?|财务回顾',
    '核数师报告': r'[^\n]{0,14}(?:核数师|审计师|审阅)报告[^\n]{0,12}',
    '财务摘要': r'(?:[^\n]{0,6})?(?:财务|业绩)(?:摘要|概要|概览)|[五十]年(?:财务)?(?:概要|摘要)',
    '综合损益表': rf'{_PFX}(?:损益(?:及其他)?(?:全面)?(?:收益|收入)?表|收益表|全面收益表|全面收入表|损益及其他全面收益(?:报)?表|利润表){_X}',
    '综合财务状况表': rf'{_PFX}(?:财务状况(?:报)?表|资产负债表){_X}',
    '综合权益变动表': rf'{_PFX}(?:股东)?权益变动(?:报)?表{_X}',
    '综合现金流量表': rf'{_PFX}现金流量(?:报)?表{_X}',
    '财务报表附注': rf'{_PFX}(?:中期)?(?:财务报表|财务资料|财务数据)附注{_X}',
}
MAIN4 = ('综合损益表', '综合财务状况表', '综合权益变动表', '综合现金流量表')
HK_NOTES = {  # 附注科目名（去掉"（续）"后）→ 正则；同名取编号最小的一条
    '收入及分部': r'收入|收益|营业额|分部',
    '除税前溢利（费用明细）': r'除税前(溢利|利润|亏损)|经营(溢利|利润)|[^\n]{0,4}(溢利|利润|亏损)(前)?$|按性质(分类|分析|划分)?的(费用|开支)',
    '所得税': r'^(综合损益[^\n]{0,10})?所得税(开支|费用|抵免)?$|^税项$|^所得税',
    '财务状况表内的所得税（递延税项）': r'财务状况表内的所得税|递延税项|递延所得税',
    '投资物业及物业厂房设备（含减值）': r'物业、?厂房及设备|投资物业',
    '使用权资产': r'使用权资产|^租赁$',
    '存货': r'^存货|发展中物业|持作(出售|销售)|开发中物业|^物业存货|待售|在建[^\n]{0,4}物业',
    '贸易及其他应收款项': r'贸易[^\n]{0,6}应收|应收[^\n]{0,4}款项|应收(贸易|账款)',
    '贸易及其他应付款项': r'贸易[^\n]{0,6}应付|应付[^\n]{0,4}款项|应付(贸易|账款)',
    '合约负债': r'合约负债|合同负债',
    '银行贷款及借款': r'银行(贷款|借款)|借款|借贷|优先票据|债券',
    '租赁负债': r'租赁负债|^租赁$',
    '现金及现金等价物': r'现金及现金等价物|现金及银行|受限制(现金|存款)|银行结余',
    '雇员福利': r'雇员福利|员工福利|职工福利|退休福利|离职后福利|员工成本|雇员成本|雇员薪酬',
    '股本、储备及股息': r'股息|股本',
    '本公司财务状况及储备（可供分派储备）': r'本公司[^\n]{0,6}(财务状况|储备|资产负债)|可供分派储备',
    '关键会计估计及判断': r'(关键|重要|重大)会计估计|会计判断|判断及估计',
    '金融风险管理': r'金融风险|财务风险',
    '承担及或然事项': r'承担|或然|担保',
    '关联方交易': r'关(联|连)(方|人士)?交易',
    '附属公司权益': r'附属公司|子公司',
    '期后事项': r'期后事项|报告期后|结算日后|期间后|日期?后[^\n]{0,6}事项|期末后',
}
HK_HINT = {'雇员福利': '员工成本多半在「除税前溢利」附注里，搜「員工成本」「薪金」'}
KAM_END = re.compile(r'^[ \t]*(其他信息|[^\n]{0,20}以外的信息|[^\n]{0,16}须承担的责任|核数师就[^\n]*承担的责任|[^\n]{0,12}对综合财务报表的责任)', re.M)
AMOUNT = re.compile(r'^[ \t]*[(（\-–—]?[\d,，.]+[)）]?[ \t]*$')
CONT = re.compile(r'[ \t]*[\-–—]?[ \t]*[（(][ \t]*续[ \t]*[)）][ \t]*$|[ \t]*[\-–—][ \t]*续$')
LATIN = re.compile(r'[A-Za-z]{3,}')
K = 12   # 每页前几行里找标题

def is_hk(text):
    """港股版式：有"核数师 / 香港财务报告准则 / 財務狀況表"这类字样，又没有 A 股的单独成行"合并资产负债表"。"""
    N = norm(text[:600000])
    if re.search(r'^[ \t]*(\d[、.．][ \t]*)?合并资产负债表[ \t]*$', N, re.M) and re.search(r'第[一二三四五六七八九十]+[节章]', N): return False
    return bool(re.search(r'核数师|香港财务报告准则|香港会计准则|财务状况(报)?表|综合资产负债表|简明综合', N))

def is_bilingual(text):
    L = [l for l in text.split('\n') if l.strip()]
    en = sum(1 for l in L if len(LATIN.findall(l)) >= 2 and not re.search(r'[一-鿿]', l))
    return len(L) > 0 and en / len(L) > 0.15

def zh_only(seg):
    """双语页只留中文：去掉没有汉字、又有英文词的行（"ASSETS""RMB’000""As at 31 December"；纯数字行、页标记留着）"""
    return '\n'.join(l for l in seg.split('\n') if not (LATIN.search(l) and not re.search(r'[一-鿿]', l)) or PAGE_RE.match(l))

def hk_pages(text, N):
    """[(页码, 起, 止, 页眉, 标题候选行)]。重复页眉 = 超过 1/5 的页前几行都有、又不是栏目名的行（公司名、报告名、
    "截至…止年度"、"人民幣千元"这类）；单双页交替的页眉各占一半页数，也算重复。"""
    from collections import Counter
    ms = list(PAGE_RE.finditer(text)); pages, heads = [], []
    for i, m in enumerate(ms):
        a = m.end(); b = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        ls = []
        for l in N[a:b].split('\n'):
            l = l.strip()
            if not l or re.fullmatch(r'[\d\s/╱|\-–—.]+', l) or (LATIN.search(l) and not re.search(r'[一-鿿]', l)): continue
            l = re.sub(r'^[\d\s/╱|]+(?=[一-鿿])', '', l)   # "125 綜合財務狀況表"
            ls.append(l)
            if len(ls) >= K: break
        heads.append(ls); pages.append((int(m.group(1)), a, b))
    cnt = Counter(l for h in heads for l in set(h))
    is_part = lambda l: any(re.fullmatch(kw, CONT.sub('', l)) for kw in HK_PART.values())
    boiler = {l for l, c in cnt.items() if c > max(3, 0.2 * len(heads)) and not is_part(l)}
    boiler |= {l for l, c in cnt.items() if c > max(3, 0.08 * len(heads)) and re.search(r'有限公司|年报|年度报告|中期报告|二零', l) and not is_part(l)}
    out = []
    for (no, a, b), h in zip(pages, heads):
        cand = [CONT.sub('', l) for l in h if l not in boiler]
        hd = next((l for l in cand if len(l) <= 30), '')
        out.append((no, a, b, hd, cand))
    return out, boiler

def hk_parts(pages):
    """栏目 → (首页, 末页, 起, 止)。每页前几行有标题行整行匹配就算命中；一页命中 3 个以上栏目是目录页，不算。
    管理层讨论 / 核数师报告 / 附注取连续命中最长的一段（中间隔 3 页以内的插图页算连着）；四张主表取核数师报告之后、附注之前第一次出现的那页，
    到下一张主表或附注开始为止（续页可能没有标题）。"""
    hit = {}
    for i, (no, a, b, hd, cand) in enumerate(pages):
        names = {name for name, kw in HK_PART.items() for l in cand if len(l) <= 40 and re.fullmatch(kw, l)}
        if len(names) >= 3: continue
        for nm in names: hit.setdefault(nm, []).append(i)
    got = {}
    for name in ('管理层讨论与分析', '核数师报告', '财务摘要', '财务报表附注'):
        best = run = None
        for i in hit.get(name, []):
            run = (run[0], i) if run and i - run[1] <= 4 else (i, i)
            if best is None or run[1] - run[0] > best[1] - best[0]: best = run
        if best: got[name] = best
    lo = got['核数师报告'][0] if '核数师报告' in got else 2
    hi = got['财务报表附注'][0] if '财务报表附注' in got else len(pages)
    for name in MAIN4:
        c = [i for i in hit.get(name, []) if lo <= i < hi] or [i for i in hit.get(name, []) if i >= 2]
        if c: got[name] = (c[0], c[0])
    starts = sorted({v[0] for k, v in got.items() if k in MAIN4} | ({got['财务报表附注'][0]} if '财务报表附注' in got else set()))
    for name in MAIN4:
        if name in got:
            s = got[name][0]; nxt = next((x for x in starts if x > s), min(len(pages), s + 3))
            got[name] = (s, min(nxt - 1, s + 6))
    return {k: (pages[s][0], pages[e][0], pages[s][1], pages[e][2]) for k, (s, e) in got.items()}

def hk_notes(N, region, boiler=()):
    """附注区里递增编号的标题 → [(编号, 科目名, 起, 止)]；下一行是金额的是表格行，重复页眉不算标题，编号不接着上一条的不算"""
    a, b = region; hs = []
    # 编号后可带 "(a)"（"9(a) 附屬公司"：没有单独的 9 号总标题）
    for m in re.finditer(r'^[ \t]*(\d{1,2})[ \t]*(?:[(（][a-z][)）])?[ \t]*(?:[.、．][ \t]*)?(?:\n[ \t]*|[ \t]+)([一-鿿][^\n]{0,40}?)[ \t]*$', N[a:b], re.M):
        if m.group(2).strip() in boiler: continue
        nxt = re.search(r'\n[ \t]*([^\n]*\S)', N[a + m.end():a + m.end() + 200])
        s = nxt.group(1).strip() if nxt else ''
        # 下一行是 "5.1"（本条的小节号）或 "9."（下一条编号）不算金额
        if nxt and AMOUNT.match(s) and not re.fullmatch(rf'(19|20)\d\d|{m.group(1)}[.．]\d{{1,2}}|\d{{1,2}}[.、．]', s): continue
        hs.append((int(m.group(1)), m.group(2), a + m.start()))
    notes = []; cur = 0
    for n, tt, p in hs:
        if n == cur + 1:
            if notes: notes[-1][3] = p
            notes.append([n, CONT.sub('', tt).strip(), p, b]); cur = n
    return [tuple(x) for x in notes]

def cut_hk(text, extra=()):
    """返回 (切好的段 [(名, 起, 止)], 没切到 [(名, 提示)], 原文定位 [(名, 页)], 各节 [(页眉, 首页)], 附注一览 [(编号, 名, 页)])"""
    N = norm(text); pg = Pages(text); pages, boiler = hk_pages(text, N); parts = hk_parts(pages)
    segs, miss, marks = [], [], []
    if '管理层讨论与分析' in parts: segs.append(('管理层讨论与分析', *parts['管理层讨论与分析'][2:]))
    else: miss.append(('管理层讨论与分析', '搜「管理層討論」「業務回顧」「財務回顧」'))
    if '财务摘要' in parts: segs.append(('财务摘要', *parts['财务摘要'][2:]))
    au = parts.get('核数师报告')
    k = re.search(r'^[ \t]*关键审计事项[ \t]*$', N[au[2]:au[3]], re.M) if au else None
    if k:
        st = au[2] + k.start(); e = KAM_END.search(N, st + 20, au[3])
        segs.append(('关键审计事项', st, e.start() if e else au[3]))
    elif au: miss.append(('关键审计事项', '搜「關鍵審計事項」（中期报告是审阅报告，没有这一节）'))
    for name in MAIN4:
        if name in parts: segs.append((name, *parts[name][2:])); marks.append((name, parts[name][0]))
        else: miss.append((name, f'搜「{name}」（繁体，或「合併」「財務狀況報表」「資產負債表」）'))
    notes = hk_notes(N, parts['财务报表附注'][2:], boiler) if '财务报表附注' in parts else []
    if '财务报表附注' not in parts: miss.append(('财务报表附注', '搜「財務報表附註」'))
    want = dict(HK_NOTES); want.update({norm(x): re.escape(norm(x)) for x in extra})
    for name, kw in want.items():
        hit = next((x for x in notes if re.search(kw, x[1])), None)
        if hit: segs.append((f'{hit[0]}_{name}', hit[2], hit[3]))
        else: miss.append((name, HK_HINT.get(name, f'搜「{name}」（繁体）') + ('' if notes else '（没认出附注编号标题）')))
    secs = []; prev = None
    cnt = {}
    for p in pages: cnt[p[3]] = cnt.get(p[3], 0) + 1
    for no, a, b, hd, _ in pages:
        if hd != prev and hd and cnt[hd] >= 2: secs.append((hd, no))
        prev = hd
    return segs, miss, marks, secs, [(n, t, pg.at(p)) for n, t, p, _ in notes]

def cut_hk_write(text, pg, outdir, title, extra, save, got, miss, trunc):
    segs, ms, marks, secs, notes = cut_hk(text, extra)
    bi = is_bilingual(text)
    for name, a, b in segs: save(name, (a, b), None if name[0].isdigit() or name == '关键审计事项' else name, zh_only if bi else None)
    miss += ms
    L = [f'# {title} 目录索引（港股版式：香港财务报告准则' + ('，中英双语，切好的段只留了中文行' if bi else '') + '）', '',
         f'全文 {pg.no[-1] if pg.no else 0} 页、{len(text)} 字：`{title}_全文.txt`（每页前一行 `=====PDF第N页=====`）。',
         '先读这份索引和下面切好的段；清单外的内容在全文里搜关键词（繁体、简体都试），只读命中的那几页，不通读全文。',
         '科目对照：綜合 / 合併財務狀況表 = 资产负债表，綜合 / 合併損益表 = 利润表，貿易應付款項 ≈ 应付账款，合約負債 ≈ 合同负债，'
         '除稅前溢利 = 利润总额，核數師 = 审计师，附屬公司 = 子公司。', '',
         '## 各节起始页（按每页页眉，重复页眉已去掉）', '']
    L += [f'- {nm}：第 {p} 页' for nm, p in secs] or ['- （没认出页眉）']
    L += ['', '## 切好的段', '', '| 段 | 页码 | 字数 | 文件 |', '|---|---|---|---|']
    L += [f'| {n}{"（截断）" if n in trunc else ""} | {s} | {c} | `{f}` |' for n, s, c, f in got]
    L += ['', '## 附注编号一览（清单外的科目按这里的页码到全文里读）', '']
    L += [f'- 附注 {n} {t}：第 {p} 页' for n, t, p in notes] or ['- （没认出附注编号标题）']
    L += ['', '## 原文定位（只给起始页）', '']
    L += [f'- {n}：第 {p} 页' for n, p in marks] or ['- 无']
    L += ['', '## 清单里没切到的（不等于报告里没有：去全文里搜，查过写"查过：…"）', '']
    L += [f'- {n}：{h}' for n, h in miss] or ['- 无']
    if trunc: L += ['', f'截断的段只存了前 {CAP} 字，后面的去全文里按页码接着读。']
    open(os.path.join(outdir, f'{title}_目录索引.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return f'{title}（港股版式{"·双语" if bi else ""}）全文{len(text)}字 / 切到 {len(got)} 段 / 没切到 {len(miss)} 项' + (f'（{"、".join(n for n, _ in miss)}）' if miss else '')

# ---------- A 股季报（没有附注、没有"第X节"）----------
# 一季报 / 三季报：只有"一、主要财务数据 /（一）主要会计数据和财务指标 /（二）非经常性损益…/ 二、股东信息 / 三、其他提醒事项 / 四、季度财务报表"，
# 后面是合并资产负债表、合并利润表、合并现金流量表（可能还有母公司报表）。按这些标题逐段切，三张合并报表也切成段（季报没有附注可看）。
Q_STMT = ('合并资产负债表', '合并利润表', '合并现金流量表')
def is_quarter(text):
    return bool(re.search(r'第[一三]季度报告|季度报告', text[:5000])) and notes_region(text) is None

def cut_quarter(text):
    """返回 [(名, 起, 止)]"""
    st = [(n, m.start()) for n in Q_STMT for m in [re.search(rf'^[ \t]*(?:\d[、.．][ \t]*)?{n}[ \t]*$', text, re.M)] if m]
    first = min((p for _, p in st), default=len(text))
    hs = [(m.group(1), m.group(2).strip(), m.start()) for m in
          re.finditer(r'^[ \t]*([一二三四五六七八九十]+、|[（(][一二三四五六七八九十]+[)）])[ \t]*([^\n]{2,40}?)[ \t]*$', text[:first], re.M)]
    segs = []
    for i, (lv, nm, p) in enumerate(hs):
        top = lv.endswith('、')
        e = next((q for lv2, _, q in hs[i + 1:] if lv2.endswith('、') or not top), first)
        nm = re.sub(r'[：:，,。]+$', '', nm)
        if e - p >= 100: segs.append((nm[:20], p, e))
    ends = sorted([p for _, p in st] + [m.start() for m in re.finditer(r'^[ \t]*母公司(资产负债表|利润表|现金流量表)[ \t]*$', text, re.M)] + [len(text)])
    for n, p in st:
        segs.append((n, p, next(e for e in ends if e > p)))
    return segs

# ---------- 主流程 ----------
def sections(text, pg):
    """各节起始页：每个"第X节 名"取最后一次出现（第一次多半在目录里）。"""
    last = {}
    for m in re.finditer(r'^[ \t]*(第[一二三四五六七八九十]+[节章])[ \t]*\n?[ \t]*([^\n]{2,30}?)[ \t.…·\d]*$', text, re.M):
        last[m.group(1)] = (m.group(2).strip(), pg.at(m.start()))
    return [(k, *v) for k, v in last.items()]

def cut(pdf, outdir, title, extra=()):
    """切一份报告，返回给 fetch_log 用的一句话。"""
    os.makedirs(outdir, exist_ok=True)
    text = pdf_text(pdf); pg = Pages(text)
    w = lambda name, s: open(os.path.join(outdir, f'{title}_{name}.txt'), 'w', encoding='utf-8').write(s)
    w('全文', text)
    got, miss, trunc, loose = [], [], [], []
    hk = is_hk(text)

    def save(name, ab, fname=None, flt=None):
        a, b = ab; seg = flt(text[a:b]) if flt else text[a:b]   # flt：双语页只留中文行
        if len(seg) > CAP and name != '管理层讨论与分析':
            b = a + int(CAP * (b - a) / len(seg)); seg = seg[:CAP]; trunc.append(name)
        span = pg.span(a, b)
        w(fname or f'附注_{name}', f'【{title}·{name}，PDF {span}】\n' + seg)
        got.append((name, span, len(seg), f'{title}_{fname or "附注_" + name}.txt'))

    if hk: return cut_hk_write(text, pg, outdir, title, extra, save, got, miss, trunc)
    if is_quarter(text):
        for name, a, b in cut_quarter(text): save(name, (a, b), name)
        for n in Q_STMT:
            if not any(g[0] == n for g in got): miss.append((n, f'搜「{n}」'))
        L = [f'# {title} 目录索引（季报：没有附注，按"一、/（一）"标题和三张合并报表切）', '',
             f'全文 {pg.no[-1] if pg.no else 0} 页、{len(text)} 字：`{title}_全文.txt`（每页前一行 `=====PDF第N页=====`）。', '',
             '## 切好的段', '', '| 段 | 页码 | 字数 | 文件 |', '|---|---|---|---|']
        L += [f'| {n}{"（截断）" if n in trunc else ""} | {s} | {c} | `{f}` |' for n, s, c, f in got]
        L += ['', '## 没切到的', ''] + ([f'- {n}：{h}' for n, h in miss] or ['- 无'])
        open(os.path.join(outdir, f'{title}_目录索引.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
        return f'{title}（季报）全文{len(text)}字 / 切到 {len(got)} 段 / 没切到 {len(miss)} 项' + (f'（{"、".join(n for n, _ in miss)}）' if miss else '')
    mda = extract_mda(text)
    if mda[1] - mda[0] >= 2000: save('管理层讨论与分析', mda, '管理层讨论与分析')
    else: miss.append(('管理层讨论与分析', '搜「管理层讨论与分析」「经营情况讨论与分析」'))

    reg = notes_region(text)
    num = dict(NUM_NOTES); num.update({k: re.escape(k) for k in extra})
    for name, kw in num.items():
        r = cut_num(text, reg, kw) if reg else None
        if r: save(name, r)
        else: miss.append((name, f'搜「{name}」' + ('' if reg else '（没找到"合并财务报表项目注释"一节）')))
    for name, kw in TOP_NOTES.items():
        try: r = cut_top(text, kw, pg)
        except Exception: r = None
        if r:
            save(name, r[:2], name if name in KEEP_NAME else None)
            if r[2]: loose.append(name)
        else: miss.append((name, f'搜「{name}」'))

    # 原文定位：第 3 页以后第一次单独成行出现的地方（跳过目录）；三张合并报表取审计报告之后的那一处
    audit = re.search(r'关键审计事项', text)
    marks = []
    for name, kw in LANDMARKS.items():
        try:
            after = audit.start() if audit and name.startswith('合并') else 0
            m = next((m for m in re.finditer(rf'^[ \t]*(?:{kw})[ \t]*$', text, re.M)
                      if m.start() >= after and pg.at(m.start()) > 2), None)
        except Exception: m = None
        if m: marks.append((name, pg.at(m.start())))
        else: miss.append((name, f'搜「{name}」'))
    for name, (st, en) in SPAN_NOTES.items():
        r = cut_span(text, st, en)
        if r: save(name, r, name)
        else: miss.append((name, f'搜「{name}」'))

    L = [f'# {title} 目录索引', '',
         f'全文 {pg.no[-1] if pg.no else 0} 页、{len(text)} 字：`{title}_全文.txt`（每页前一行 `=====PDF第N页=====`）。',
         '先读这份索引和下面切好的段；清单外的内容在全文里搜关键词，只读命中的那几页，不通读全文。', '',
         '## 各节起始页', '']
    L += [f'- {k} {nm}：第 {p} 页' for k, nm, p in sections(text, pg)] or ['- （没认出"第X节"标题）']
    L += ['', '## 切好的段', '', '| 段 | 页码 | 字数 | 文件 |', '|---|---|---|---|']
    L += [f'| {n}{"（截断）" if n in trunc else ""}{"（标题无编号，取到下一页末，结尾可能多出别的内容）" if n in loose else ""} | {s} | {c} | `{f}` |' for n, s, c, f in got]
    L += ['', '## 原文定位（只给起始页，到全文里读那几页）', '']
    L += [f'- {n}：第 {p} 页' for n, p in marks] or ['- 无']
    L += ['', '## 清单里没切到的（不等于报告里没有：去全文里搜，查过写"查过：…"）', '']
    L += [f'- {n}：{h}' for n, h in miss] or ['- 无']
    if trunc: L += ['', f'截断的段只存了前 {CAP} 字，后面的去全文里按页码接着读。']
    open(os.path.join(outdir, f'{title}_目录索引.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    return f'{title} 全文{len(text)}字 / 切到 {len(got)} 段 / 没切到 {len(miss)} 项' + (f'（{"、".join(n for n, _ in miss)}）' if miss else '')

if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opt = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
    if not args or not os.path.isfile(args[0]): sys.exit(__doc__)
    pdf = args[0]; out = args[1] if len(args) > 1 else os.path.dirname(os.path.abspath(pdf))
    title = opt.get('title') or os.path.splitext(os.path.basename(pdf))[0]
    print(cut(pdf, out, title, [k for k in opt.get('notes', '').split(',') if k]))
