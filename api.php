<?php
require __DIR__.'/config.php';
$action=$_GET['action']??'catalog';$catalog=products();
if($action==='catalog')respond(['products'=>$catalog,'stores'=>array_values(array_unique(array_column($catalog,'store')))]);
if($action==='orders')respond(['orders'=>orders()]);
if($action==='track'){$id=trim($_GET['id']??'');foreach(orders() as $o)if($o['id']===$id)respond(['order'=>$o]);respond(['error'=>'Order not found'],404);}
if($action==='checkout'){
 if($_SERVER['REQUEST_METHOD']!=='POST')respond(['error'=>'POST required'],405);
 $body=json_decode(file_get_contents('php://input'),true);$cart=$body['items']??[];
 if(!is_array($cart)||!count($cart)||count($cart)>100)respond(['error'=>'Cart must contain 1–100 lines'],400);
 $byid=array_column($catalog,null,'id');$lines=[];$totals=[];
 foreach($cart as $line){$id=$line['id']??'';$qty=filter_var($line['qty']??null,FILTER_VALIDATE_INT);if(!isset($byid[$id])||$qty===false||$qty<1||$qty>99)respond(['error'=>'Invalid product or quantity'],400);$product=$byid[$id];if($qty>$product['stock'])respond(['error'=>'Insufficient stock for '.$product['name'].' at '.$product['store']],409);$subtotal=round($qty*$product['price'],2);$lines[]=['id'=>$id,'name'=>$product['name'],'store'=>$product['store'],'qty'=>$qty,'unit_price'=>$product['price'],'subtotal'=>$subtotal];$totals[$product['store']]=round(($totals[$product['store']]??0)+$subtotal,2);}
 $delivery=round(count($totals)*24.99,2);$subtotal=round(array_sum($totals),2);
 $order=['id'=>'SS'.date('ymd').strtoupper(bin2hex(random_bytes(3))),'created_at'=>date(DATE_ATOM),'status'=>'Placed','timeline'=>[['status'=>'Placed','at'=>date(DATE_ATOM)]],'items'=>$lines,'store_totals'=>$totals,'subtotal'=>$subtotal,'delivery'=>$delivery,'total'=>round($subtotal+$delivery,2),'mode'=>'SIMULATED - NO PAYMENT'];
 $f=fopen(DATA_DIR.'/orders.json','c+');if(!$f)respond(['error'=>'Order storage unavailable'],500);flock($f,LOCK_EX);$raw=stream_get_contents($f);$all=json_decode($raw,true)?:[];$all[]=$order;rewind($f);ftruncate($f,0);fwrite($f,json_encode($all,JSON_PRETTY_PRINT));fflush($f);flock($f,LOCK_UN);fclose($f);respond(['order'=>$order]);
}
if($action==='advance'){
 if($_SERVER['REQUEST_METHOD']!=='POST')respond(['error'=>'POST required'],405);
 $body=json_decode(file_get_contents('php://input'),true)?:[];$id=$body['id']??'';$states=['Placed','Confirmed','Picking','Consolidating','Out for delivery','Delivered'];
 $f=fopen(DATA_DIR.'/orders.json','c+');if(!$f)respond(['error'=>'Storage unavailable'],500);flock($f,LOCK_EX);$all=json_decode(stream_get_contents($f),true)?:[];$found=null;
 foreach($all as &$o)if($o['id']===$id){$index=array_search($o['status'],$states,true);if($index!==false&&$index<count($states)-1){$o['status']=$states[$index+1];$o['timeline'][]=['status'=>$o['status'],'at'=>date(DATE_ATOM)];}$found=$o;break;}unset($o);
 if(!$found){flock($f,LOCK_UN);fclose($f);respond(['error'=>'Order not found'],404);}rewind($f);ftruncate($f,0);fwrite($f,json_encode($all,JSON_PRETTY_PRINT));fflush($f);flock($f,LOCK_UN);fclose($f);respond(['order'=>$found]);
}
if($action==='chat'){
 $body=json_decode(file_get_contents('php://input'),true)?:[];$q=trim((string)($body['message']??''));if(strlen($q)>500)respond(['answer'=>'Please shorten your question.']);$lower=strtolower($q);
 if(!$q)respond(['answer'=>'Ask about product prices, stock, cheapest stores, deals, orders or delivery.']);
 if(preg_match('/(track|order status|where is my order)/',$lower))respond(['answer'=>'Open Track Order and enter your ShopSmart order ID. Orders are locally simulated, not connected to courier systems.']);
 if(preg_match('/(delivery|shipping|checkout|consolidat)/',$lower))respond(['answer'=>'Your multi-store cart is consolidated into one ShopSmart order. This demo charges R24.99 delivery per participating store and shows a retailer-by-retailer cost split. No real payment or dispatch occurs.']);
 if(preg_match('/(privacy|personal data|secure)/',$lower))respond(['answer'=>'This demo stores orders locally in JSON and does not collect card numbers. Do not enter sensitive personal data. Production deployment requires authentication, encryption, access controls and POPIA review.']);
 if(preg_match('/(sales|popular|best.sell)/',$lower)){$r=$catalog;usort($r,fn($a,$b)=>$b['sales_30d']<=>$a['sales_30d']);$r=array_slice($r,0,5);respond(['answer'=>'Highest 30-day demo sales: '.implode('; ',array_map(fn($x)=>$x['name'].' at '.$x['store'].' ('.$x['sales_30d'].' units)',$r)).'.']);}
 $matches=[];foreach($catalog as $x){$name=strtolower($x['name']);$terms=preg_split('/\s+/',preg_replace('/[^a-z0-9 ]/',' ',strtolower($x['name'])));$hits=0;foreach($terms as $term)if(strlen($term)>2&&str_contains($lower,$term))$hits++;if(str_contains($lower,$name)||$hits>0)$matches[]=$x;}
 if($matches){$requestedStore=null;foreach(array_unique(array_column($catalog,'store')) as $s)if(str_contains($lower,strtolower($s)))$requestedStore=$s;if($requestedStore)$matches=array_values(array_filter($matches,fn($x)=>$x['store']===$requestedStore));usort($matches,fn($a,$b)=>$a['price']<=>$b['price']);$matches=array_slice($matches,0,8);if(!$matches)respond(['answer'=>'No matching product found for that retailer in the demonstration catalogue.']);$answer='Catalogue matches (sample prices, not live): '.implode('; ',array_map(fn($x)=>$x['name'].' — '.$x['store'].' R'.number_format($x['price'],2).' ('.$x['stock'].' in stock)',$matches));respond(['answer'=>$answer]);}
 if(preg_match('/(stock|inventory|low stock)/',$lower)){$low=array_values(array_filter($catalog,fn($x)=>$x['stock']<6));respond(['answer'=>count($low).' demo catalogue entries have fewer than 6 units. Examples: '.implode('; ',array_map(fn($x)=>$x['name'].' at '.$x['store'].' ('.$x['stock'].')',array_slice($low,0,6))).'.']);}
 if(preg_match('/(store|retailer|shop)/',$lower))respond(['answer'=>'ShopSmart compares Pick n Pay, Shoprite, Woolworths, Checkers, Boxer and SPAR. Ask, for example, “cheapest milk”, “rice stock”, “coffee prices at SPAR” or “top sales”.']);
 respond(['answer'=>'I use the 120-row demonstration catalogue and stock data. Try “compare milk prices”, “where is bread cheapest?”, “stock for eggs”, “top sales”, “delivery fee”, or “track order”.']);
}
respond(['error'=>'Unknown action'],404);
