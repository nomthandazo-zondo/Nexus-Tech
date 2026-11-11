<?php
const DATA_DIR = __DIR__ . '/data';
function products(): array { $r=[]; $f=fopen(DATA_DIR.'/products.csv','r'); $h=fgetcsv($f); while(($a=fgetcsv($f))!==false){$v=array_combine($h,$a);$v['price']=(float)$v['price'];$v['stock']=(int)$v['stock'];$v['sales_30d']=(int)$v['sales_30d'];$v['original_price']=(float)$v['original_price'];$r[]=$v;}fclose($f);return $r; }
function orders():array {return json_decode(file_get_contents(DATA_DIR.'/orders.json'),true)?:[];}
function respond($data,$status=200){http_response_code($status);header('Content-Type: application/json; charset=utf-8');header('Cache-Control: no-store');echo json_encode($data,JSON_UNESCAPED_SLASHES);exit;}
