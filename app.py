# -*- coding: utf-8 -*-
# app.py

import streamlit as st
import pandas as pd
import numpy as np
import regex, re, unicodedata
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from deep_translator import GoogleTranslator
import spacy, spacy.cli
import spacy
import scipy.sparse as sp
import spacy
from spacy.cli import download as spacy_download
import spacy.cli
try:
    spacy.load("en_core_web_sm")
except OSError:
    spacy.cli.download("en_core_web_sm")


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import train_test_split
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, RocCurveDisplay, ConfusionMatrixDisplay

from gensim import corpora, models, similarities
from gensim.models import Word2Vec, FastText

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.ml.feature import RegexTokenizer, StopWordsRemover, HashingTF, IDF
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml.classification import LogisticRegression as SparkLR, DecisionTreeClassifier as SparkDT, RandomForestClassifier as SparkRF

# ─── Page config & Sidebar ─────────────────────────────────────────────────────
st.set_page_config(page_title="ITViec Explorer", layout="wide")
with st.sidebar:
    st.title("🔍 ITViec Explorer")
    menu = st.radio("☰ Menu", [
        "🗂 Upload Data",
        "📊 EDA & WordCloud",
        "🔍 Similarity Search",
        "🤖 Recommendation"
    ])
    st.markdown("---")
    st.markdown("### 👤 Thành viên")
    st.markdown("- Nguyễn Lư Bảo Khang (nbaokhang12@gmail.com)")
    st.markdown("- Phạm Đức Huy (DucHuyUFM@gmail.com)")
    st.markdown("**GVHD:** Ms. Khuất Thùy Phương")
    st.markdown("Đồ án Tốt nghiệp  \nData Science & ML  \nTTTH - ĐH KHTN")

# ─── 1) Introduction (always visible) ─────────────────────────────────────────
st.header("📝 Giới thiệu")
st.markdown("""
**ITViec** là nền tảng việc làm IT hàng đầu Việt Nam.
- Hơn 8.000 đánh giá nhân viên & cựu nhân viên.
- Các trường chính: *What I liked*, *Suggestions for improvement*, *Company Name*, *id*, *Recommend?*, *Overall Rating*,…
- Dữ liệu được dịch (Vi→En), chuẩn hóa & lọc từ loại trước khi dùng ML.

**Mục tiêu**
1. **Content-Based Similarity** (Overview & Reviews qua TF-IDF, Gensim-TFIDF, Word2Vec, FastText và numeric ratings)
2. **Recommendation Classification** (Scikit-Learn: LR, RF, SVM, XGB; PySpark: LR, DT, RF; interactive)
""")

# ─── 2) Text tools & clean_text ─────────────────────────────────────────────────
@st.cache_data
def init_text_tools():
    tr = GoogleTranslator(source="auto", target="en")
    try:
        nlp = spacy.load("en_core_web_sm", disable=["parser","ner"])
    except OSError:
        spacy_download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm", disable=["parser","ner"])
    sw  = spacy.lang.en.stop_words.STOP_WORDS
    vn  = re.compile(r"[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗơớờởỡợùúủũụưứừửữựỳỷỹự]", re.IGNORECASE)
    return tr, nlp, sw, vn

translator, nlp, EN_SW, VIET_REGEX = init_text_tools()

@st.cache_data
def clean_text(txt: str) -> str:
    s = str(txt).strip()
    if VIET_REGEX.search(s):
        try: s = translator.translate(s)
        except: pass
    s = unicodedata.normalize("NFD", s)
    s = regex.sub(r"\p{Mn}", "", s)
    s = re.sub(r"[^A-Za-z\s]", " ", s).lower()
    toks = [w for w in re.findall(r"\b\w\w+\b", s) if w not in EN_SW]
    doc  = nlp(" ".join(toks))
    return " ".join(tok.text for tok in doc if tok.pos_ in {"NOUN","VERB","ADJ","ADV"})

# ─── 3) Upload Data ─────────────────────────────────────────────────────────────
if menu == "🗂 Upload Data":
    st.subheader("1️⃣ Upload dữ liệu")
    if "df_comp" not in st.session_state:
        src = st.selectbox("Chọn nguồn:", ["A. Raw Excel (3 files)", "B. Preprocessed CSV + Reviews.xlsx"])
        if src.startswith("A"):
            comp_fp = st.file_uploader("Overview_Companies.xlsx", type="xlsx")
            map_fp  = st.file_uploader("Overview_Reviews.xlsx",  type="xlsx")
            rev_fp  = st.file_uploader("Reviews.xlsx",          type="xlsx")
            if comp_fp and map_fp and rev_fp:
                st.session_state.src = "A"
                st.session_state.comp_fp = comp_fp
                st.session_state.map_fp  = map_fp
                st.session_state.rev_fp  = rev_fp
                st.success("✅ Đã upload 3 file raw.")
        else:
            comp_fp = st.file_uploader("df_comp_clean.csv",       type="csv")
            all_fp  = st.file_uploader("df_all_preprocessed.csv", type="csv")
            map_fp  = st.file_uploader("Overview_Reviews.xlsx",   type="xlsx")
            if comp_fp and all_fp and map_fp:
                st.session_state.src    = "B"
                st.session_state.comp_fp = comp_fp
                st.session_state.all_fp  = all_fp
                st.session_state.map_fp  = map_fp
                st.success("✅ Đã upload CSV & XLSX.")
    else:
        st.info("✅ Dữ liệu đã sẵn sàng trong session.")
    st.stop()

# ─── 4) Load & Preprocess ───────────────────────────────────────────────────────
@st.cache_data
def load_all(src, comp_fp, map_fp, rev_fp_or_all_fp):
    if src == "A":
        df_comp = pd.read_excel(comp_fp)
        df_map  = pd.read_excel(map_fp)
        df_rev  = pd.read_excel(rev_fp_or_all_fp)
        df_comp["Clean_desc"] = df_comp["Company overview"].fillna("").map(clean_text)
        df_rev["Clean_rev"]   = (
            df_rev["What I liked"].fillna("") + " " +
            df_rev["Suggestions for improvement"].fillna("")
        ).map(clean_text)
        df_all = (
            df_map
            .merge(df_rev, on="id", how="inner")
            .merge(df_comp[["id","Company Name","Clean_desc"]], on="id", how="inner")
        )
    else:
        # src == "B"
        df_comp = pd.read_csv(comp_fp)
        df_map  = pd.read_excel(map_fp)
        df_all  = pd.read_csv(rev_fp_or_all_fp)
        df_comp["Clean_desc"] = df_comp["Clean_desc"].fillna("")
        df_all["Clean_rev"]   = df_all["Clean_rev"].fillna("")

    # numeric ratings
    df_map_num = df_map.select_dtypes(include="number").fillna(0).copy()
    df_map_num["id"] = df_map["id"]

    # merge overview, reviews, ratings
    df_all = (
        df_all
        .merge(df_map_num, on="id", how="left")
        .merge(df_comp[["id","Company Name","Clean_desc"]], on="id", how="left")
    )
    df_all["Clean_rev"] = df_all["Clean_rev"].fillna("")
    df_all["Label"]     = (df_all["Recommend?"].str.lower() == "yes").astype(int)

    return df_comp, df_map_num, df_all

# Thay vì load_all(st.session_state), gọi:
src = st.session_state["src"]         # hoặc "A"/"B"
fp1 = st.session_state["comp_fp"]
fp2 = st.session_state["map_fp"]
fp3 = st.session_state["rev_fp"] if src=="A" else st.session_state["all_fp"]

df_comp, df_map, df_all = load_all(src, fp1, fp2, fp3)
COMP_NAMES = df_comp["Company Name"].tolist()

# ─── 5) EDA & WordCloud ────────────────────────────────────────────────────────
if menu == "📊 EDA & WordCloud":
    st.header("2️⃣ EDA & WordCloud")
    t1,t2,t3 = st.tabs(["Companies","Numeric Ratings","Reviews"])
    with t1:
        st.subheader("Companies")
        st.dataframe(df_comp)
        txt = " ".join(df_comp["Clean_desc"])
        st.image(WordCloud(width=600,height=400).generate(txt).to_array(), use_column_width=True)
    with t2:
        st.subheader("Numeric Ratings")
        st.dataframe(df_map)
        st.bar_chart(df_map.set_index("id").mean())
    with t3:
        st.subheader("Reviews")
        st.dataframe(df_all[["Clean_rev","Recommend?","Label"]])
        txt2 = " ".join(df_all["Clean_rev"])
        st.image(WordCloud(width=600,height=400).generate(txt2).to_array(), use_column_width=True)
    st.stop()

# ─── 6) Similarity Search ──────────────────────────────────────────────────────
if menu == "🔍 Similarity Search":
    st.header("3️⃣ Similarity Search")
    idx = st.selectbox("Chọn công ty", range(len(COMP_NAMES)), format_func=lambda i:COMP_NAMES[i])
    cid = df_comp.at[idx,"id"]

    # helper: topn table
    def show_topn(arr, labels):
        df = pd.DataFrame({"Company":labels,"Score":arr})
        return df.sort_values("Score",ascending=False).iloc[1:6].style.format({"Score":"{:.2%}"})

    # Numeric
    sim_num = cosine_similarity(df_map.drop("id", axis=1).values)[idx]
    st.subheader("• Numeric Ratings"); st.table(show_topn(sim_num,COMP_NAMES))

    # Overview TF-IDF
    tf    = TfidfVectorizer(ngram_range=(1,2),max_features=3000)
    M_tf  = tf.fit_transform(df_comp["Clean_desc"])
    st.subheader("• Overview TF-IDF"); st.table(show_topn(cosine_similarity(M_tf)[idx],COMP_NAMES))

    # Gensim-TFIDF
    toks = [t.split() for t in df_comp["Clean_desc"]]
    dct  = corpora.Dictionary(toks)
    corp_= [dct.doc2bow(t) for t in toks]
    mgt  = models.TfidfModel(corp_)
    idxs = similarities.MatrixSimilarity(mgt[corp_], num_features=len(dct))
    SIM_GS = np.vstack([ idxs[mgt[corp_][i]] for i in range(len(corp_)) ])
    st.subheader("• Overview Gensim-TFIDF"); st.table(show_topn(SIM_GS[idx],COMP_NAMES))

    # Word2Vec & FastText (IDF-weighted)
    idf = tf.idf_
    def idf_sim(model):
        mat=[]
        for doc in toks:
            vecs, ws = [], []
            for w in doc:
                if w in model.wv:
                    vecs.append(model.wv[w]); ws.append(idf[tf.vocabulary_.get(w,0)])
            mat.append(np.average(vecs,axis=0,weights=ws) if vecs else np.zeros(model.vector_size))
        return cosine_similarity(np.vstack(mat))[idx]
    st.subheader("• Overview Word2Vec"); st.table(show_topn(idf_sim(Word2Vec(toks,vector_size=100,window=5,min_count=2,epochs=10)),COMP_NAMES))
    st.subheader("• Overview FastText"); st.table(show_topn(idf_sim(FastText(toks,vector_size=100,window=5,min_count=2,epochs=10)),COMP_NAMES))

        # --- Reviews tương tự ---
    # 1) Group & reindex theo df_comp["id"]
    rev_grp = (
        df_all
        .groupby("id")["Clean_rev"]
        .apply(" ".join)
        .reindex(df_comp["id"])
        .fillna("")
    )

    # 2) Reviews TF-IDF
    tf_r    = TfidfVectorizer(ngram_range=(1,2), max_features=3000)
    M_rtf   = tf_r.fit_transform(rev_grp)
    sim_rtf = cosine_similarity(M_rtf)[idx]
    st.subheader("• Reviews TF-IDF")
    df_rtf  = pd.DataFrame({"Company":COMP_NAMES, "Score":sim_rtf}).iloc[1:6]
    st.table(df_rtf.style.format({"Score":"{:.2%}"}))

    # 3) Reviews Gensim-TFIDF
    toks_r = [doc.split() for doc in rev_grp]
    dct_r  = corpora.Dictionary(toks_r)
    corp_r = [dct_r.doc2bow(doc) for doc in toks_r]
    tfidf_r= models.TfidfModel(corp_r)
    idx_r  = similarities.MatrixSimilarity(tfidf_r[corp_r], num_features=len(dct_r))
    GEN_rv = np.vstack([ idx_r[tfidf_r[corp_r][i]] for i in range(len(corp_r)) ])
    sim_rgs= GEN_rv[idx]
    st.subheader("• Reviews Gensim-TFIDF")
    df_rgs = pd.DataFrame({"Company":COMP_NAMES, "Score":sim_rgs}).iloc[1:6]
    st.table(df_rgs.style.format({"Score":"{:.2%}"}))

    # 4) Reviews Word2Vec (IDF-weighted)
    idf_r   = tf_r.idf_
    w2v_r   = Word2Vec(toks_r, vector_size=100, window=5, min_count=2, epochs=10)
    def weighted_matrix(model, docs, idf, vocab):
        mat = []
        for doc in docs:
            vecs, ws = [], []
            for w in doc:
                if w in model.wv:
                    vecs.append(model.wv[w])
                    ws.append(idf[vocab.get(w,0)])
            mat.append(np.average(vecs, axis=0, weights=ws) if vecs else np.zeros(model.vector_size))
        return np.vstack(mat)
    mat_w2_r = weighted_matrix(w2v_r, toks_r, idf_r, tf_r.vocabulary_)
    sim_rw2  = cosine_similarity(mat_w2_r)[idx]
    st.subheader("• Reviews Word2Vec")
    df_rw2   = pd.DataFrame({"Company":COMP_NAMES, "Score":sim_rw2}).iloc[1:6]
    st.table(df_rw2.style.format({"Score":"{:.2%}"}))

    # 5) Reviews FastText (IDF-weighted)
    ft_r     = FastText(toks_r, vector_size=100, window=5, min_count=2, epochs=10)
    mat_ft_r = weighted_matrix(ft_r, toks_r, idf_r, tf_r.vocabulary_)
    sim_rft  = cosine_similarity(mat_ft_r)[idx]
    st.subheader("• Reviews FastText")
    df_rft   = pd.DataFrame({"Company":COMP_NAMES, "Score":sim_rft}).iloc[1:6]
    st.table(df_rft.style.format({"Score":"{:.2%}"}))
    st.stop()

# ─── 7) Recommendation Classification ─────────────────────────────────────────
if menu == "🤖 Recommendation":
    st.header("4️⃣ Recommendation Classification")

    # --- Chuẩn bị dữ liệu ---
    tv = TfidfVectorizer(max_features=3000)
    Xr = tv.fit_transform(df_all["Clean_rev"].fillna(""))
    df_map_num = (
        df_map
        .set_index("id")
        .select_dtypes(include="number")
        .fillna(0)
    )
    num_mat = df_map_num.loc[df_all["id"]].values
    Xn      = sp.csr_matrix(num_mat)
    X       = sp.hstack([Xr, Xn])
    y       = df_all["Label"]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=42,
        stratify=y if y.nunique()>1 else None
    )
    X_res, y_res = SMOTE(random_state=42).fit_resample(X_tr, y_tr)

    # --- Scikit-Learn models (cached) ---
    @st.cache_data(show_spinner=False)
    def train_sk_models(_X_res, _y_res, _X_te, _y_te):
        clfs = {
            "LR":  LogisticRegression(class_weight="balanced", max_iter=500),
            "RF":  RandomForestClassifier(class_weight="balanced"),
            "SVM": SVC(probability=True, class_weight="balanced"),
            "XGB": XGBClassifier(use_label_encoder=False, eval_metric="logloss")
        }
        results = {}
        for name, clf in clfs.items():
            clf.fit(_X_res, _y_res)
            p    = clf.predict(_X_te)
            prob = clf.predict_proba(_X_te)[:,1]
            results[name] = {
                "pred": p,
                "prob": prob,
                "Acc":  accuracy_score(_y_te, p),
                "Prec": precision_score(_y_te, p, zero_division=0),
                "Rec":  recall_score(_y_te, p, zero_division=0),
                "F1":   f1_score(_y_te, p, zero_division=0),
                "AUC":  roc_auc_score(_y_te, prob)
            }
        return results

    sk_res = train_sk_models(X_res, y_res, X_te, y_te)

    # --- PySpark models (cached resource) ---
    @st.cache_resource(show_spinner=False)
    def train_spark_models(df_all):
        spark = SparkSession.builder.appName("itviec_cls").getOrCreate()
        sdf = spark.createDataFrame(
            df_all[["Clean_rev","Label"]]
            .rename(columns={"Clean_rev":"text","Label":"label"})
        )
        tok  = RegexTokenizer(inputCol="text",    outputCol="words",      pattern="\\W+")
        rem  = StopWordsRemover(inputCol="words",  outputCol="filtered")
        htf  = HashingTF(inputCol="filtered",      outputCol="rawFeatures", numFeatures=3000)
        idf  = IDF(inputCol="rawFeatures",         outputCol="features")
        pipe = Pipeline(stages=[tok, rem, htf, idf])
        data = pipe.fit(sdf).transform(sdf).select("features","label")
        tr, te = data.randomSplit([0.8,0.2], seed=42)

        ev_acc  = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="accuracy")
        ev_prec = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="weightedPrecision")
        ev_rec  = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="weightedRecall")
        ev_f1   = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="f1")
        ev_auc  = BinaryClassificationEvaluator(   labelCol="label", rawPredictionCol="probability", metricName="areaUnderROC")

        models_sp = {
            "SparkLR": SparkLR(labelCol="label", featuresCol="features"),
            "SparkDT": SparkDT(labelCol="label", featuresCol="features"),
            "SparkRF": SparkRF(labelCol="label", featuresCol="features")
        }
        sp_metrics = {}
        sp_preds   = {}
        for nm, est in models_sp.items():
            m   = est.fit(tr)
            prd = m.transform(te).withColumn("prediction", col("prediction").cast("double"))
            sp_metrics[nm] = {
                "Acc":  ev_acc.evaluate(prd),
                "Prec": ev_prec.evaluate(prd),
                "Rec":  ev_rec.evaluate(prd),
                "F1":   ev_f1.evaluate(prd),
                "AUC":  ev_auc.evaluate(prd)
            }
            sp_preds[nm] = prd.select("label","prediction","probability").toPandas()
        spark.stop()
        return sp_metrics, sp_preds

    sp_res, sp_preds = train_spark_models(df_all)

    # --- Hiển thị 3 tab ---
    tab1, tab2, tab3 = st.tabs(["🔹 Scikit-Learn","🔸 PySpark","🤖 Interactive"])

    # Tab Scikit-Learn
    with tab1:
        st.subheader("Scikit-Learn Metrics")
        df_sk = pd.DataFrame({
            nm: {**{k:v for k,v in stats.items() if k in ["Acc","Prec","Rec","F1","AUC"]}}
            for nm,stats in sk_res.items()
        }).T
        st.dataframe(df_sk.style.format("{:.2%}"))

        # Confusion Matrix
        fig, axes = plt.subplots(2,2,figsize=(12,10)); axes=axes.flatten()
        for ax,(nm,stats) in zip(axes, sk_res.items()):
            ConfusionMatrixDisplay.from_predictions(y_te, stats["pred"], ax=ax)
            ax.set_title(nm)
        st.pyplot(fig)

        # ROC Curves
        fig2, ax2 = plt.subplots(figsize=(6,6))
        for nm,stats in sk_res.items():
            RocCurveDisplay.from_predictions(y_te, stats["prob"], name=nm, ax=ax2)
        st.pyplot(fig2)

    # Tab PySpark
    with tab2:
        st.subheader("PySpark Metrics")
        df_sp = pd.DataFrame(sp_res).T
        st.dataframe(df_sp.style.format("{:.2%}"))

        # Confusion Matrices
        cols = len(sp_preds)
        fig3, axes3 = plt.subplots(1, cols, figsize=(5*cols,4))
        if cols==1: axes3=[axes3]
        for ax,(nm,pdf) in zip(axes3, sp_preds.items()):
            ConfusionMatrixDisplay.from_predictions(
                pdf["label"].astype(int),
                pdf["prediction"].astype(int),
                ax=ax
            )
            ax.set_title(nm)
        st.pyplot(fig3)

        # ROC Curves
        fig4, ax4 = plt.subplots(figsize=(6,6))
        for nm,pdf in sp_preds.items():
            scores = pdf["probability"].apply(lambda v: v[1])
            RocCurveDisplay.from_predictions(pdf["label"].astype(int), scores, name=nm, ax=ax4)
        st.pyplot(fig4)

    # Tab Interactive
    with tab3:
        st.subheader("Interactive Prediction")
        best = max(sk_res.items(), key=lambda x: x[1]["Acc"])[0]
        st.markdown(f"**Best model:** {best}")
        clf = {
            "LR":  LogisticRegression(class_weight="balanced", max_iter=500),
            "RF":  RandomForestClassifier(class_weight="balanced"),
            "SVM": SVC(probability=True, class_weight="balanced"),
            "XGB": XGBClassifier(use_label_encoder=False, eval_metric="logloss")
        }[best]
        clf.fit(X_res, y_res)

        q = st.text_input("Nhập partial tên công ty để dự đoán Recommend?")
        if q:
            mask = df_all["Company Name"].str.contains(q, case=False, na=False)
            if not mask.any():
                st.warning("Không tìm thấy công ty.")
            else:
                Xq   = X[mask.values]
                pr   = clf.predict_proba(Xq)[:,1]
                st.metric("Recommend rate", f"{(pr>0.5).mean():.2%}")

                df_detail = pd.DataFrame({
                    "Review": df_all.loc[mask, "Clean_rev"],
                    "Prob":   [f"{x:.2%}" for x in pr]
                })
                st.dataframe(df_detail, use_container_width=True)
