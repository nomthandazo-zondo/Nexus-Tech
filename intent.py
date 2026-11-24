import csv,json
from pathlib import Path
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report,accuracy_score,confusion_matrix
from sklearn.model_selection import train_test_split
ROOT=Path(__file__).resolve().parent
EXAMPLES={
'add':'add milk|put bread in basket|I need rice|buy eggs|get me chicken|I want oats|throw apples into my cart|please include soap|can I have two bananas|pop flour in my basket|put in some sugar|grab coffee for me|addd bred|I would like pasta|basket needs cheese',
'remove':'remove milk|delete bread|take rice out|drop eggs from basket|do not want chicken anymore|remove one apple|get rid of soap|take away sugar|exclude coffee from cart|discard pasta|subtract cheese|remov bred|undo adding oats|take bananas off my list|remove flour please',
'compare':'compare milk prices|which store is cheapest for bread|price comparison rice|how much are eggs|cost of chicken across stores|where is soap cheaper|compare apples|best price for sugar|how much does coffee cost|show pasta prices|cheapest cheese|compair bred|price of oats|compare bananas between retailers|which retailer sells flour cheapest',
'browse':'browse dairy|list products|show catalog|search for rice|find eggs|what groceries are available|display household goods|browse Shoprite|show vegetables|list bakery items|looking for coffee|browse beverages|show available products|search the shelves|what do you sell',
'cart':'show cart|view basket|what is in my cart|basket total|display my shopping bag|check my cart|review basket|list my selected items|how much is my basket|what have I added|open my cart|show my shopping list|see basket|view selected groceries|cart contents',
'budget':'recommend groceries under R300|budget R500|what can I afford|shopping on a budget|meal plan for R200|suggest groceries for R100|I have R400 for food|help me stretch R250|groceries within R600|budget friendly basket|food for R150|spend no more than R450|recommend a cheap basket|plan my grocery budget|shop within R1000',
'optimise':'optimise basket|optimize cart|reduce my basket cost|find cheaper combination|minimise delivery fees|save money on entire cart|consolidate my basket|best stores for my order|reallocate groceries|cheaper total order|optimise my shopping|reduce total shopping bill|compare complete basket cost|find optimal retailer mix|save on my whole basket',
'checkout':'checkout|place order|order now|buy basket|proceed to checkout|finish shopping|submit my basket|pay for my order|complete purchase|check out please|finalise order|ready to order|start checkout|review payment total|purchase my cart',
'track':'track order|where is my delivery|order status|show orders|track my parcel|when will my order arrive|view order history|check shipment|delivery progress|locate my order|has my order arrived|show past purchases|track package|status of delivery|check my previous order',
'feedback':'suggestion: more items|feedback: great app|send developer feedback|report a suggestion|I have feedback|tell developers to improve|submit a comment|suggestion: add stores|feedback for team|report an issue|developer suggestion|send my opinion|leave a review|give app feedback|suggest an improvement',
'other':'hello|how are you|tell me a joke|what is the capital of France|thanks|good morning|explain gravity|who are you|what can you do|what is AI|how is your day|goodbye|tell me about music|help|write a poem'}
def train():
 def load(name):
  with (ROOT/'data'/name).open(encoding='utf8',newline='') as f:
   return [(r['text'],r['intent']) for r in csv.DictReader(f)]
 a,c=zip(*load('intents.csv')); b,d=zip(*load('intents_test.csv')); y=c+d
 assert not set(t.casefold() for t in a)&set(t.casefold() for t in b)
 model=make_pipeline(TfidfVectorizer(analyzer='char_wb',ngram_range=(2,5),sublinear_tf=True),LogisticRegression(max_iter=1000,C=8))
 model.fit(a,c); pred=model.predict(b); labels=sorted(set(y))
 report={'training':len(a),'testing':len(b),'accuracy':accuracy_score(d,pred),'classification':classification_report(d,pred,output_dict=True,zero_division=0),'labels':labels,'confusion_matrix':confusion_matrix(d,pred,labels=labels).tolist()}
 return model,report,list(zip(b,d,pred))
if __name__=='__main__':
 model,report,pred=train(); (ROOT/'docs').mkdir(exist_ok=True)
 (ROOT/'docs'/'evaluation.json').write_text(json.dumps(report,indent=2))
 with (ROOT/'docs'/'test_predictions.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['text','actual','predicted']);w.writerows(pred)
 print(json.dumps({k:report[k] for k in ['training','testing','accuracy']},indent=2))
