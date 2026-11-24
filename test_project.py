import unittest,tempfile
from pathlib import Path
import shopsmart as s
from advanced import quote,optimise
from auth import Accounts
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=s.DB;s.DB=Path(self.tmp.name)/'demo.db';self.e=s.Engine(1)
 def tearDown(self):self.e.conn.close();s.DB=self.old;self.tmp.cleanup()
 def test_catalog(self):self.assertEqual(len(self.e.products),200)
 def test_add(self):self.e.local('add 2 milk and bread');self.assertEqual(sum(q for p,q in self.e.cart()),3)
 def test_typo(self):self.e.local('addd bred');self.assertEqual(len(self.e.cart()),1)
 def test_remove(self):self.e.local('add milk');self.e.local('remove milk');self.assertFalse(self.e.cart())
 def test_optimise(self):
  self.e.local('add milk from Woolworths');self.e.local('add bread');old=quote(self.e.cart())[1];self.e.local('optimise basket');self.e.local('confirm optimise');self.assertLessEqual(quote(self.e.cart())[1],old)
 def test_checkout(self):
  self.e.local('add milk');self.e.local('checkout');self.assertTrue(self.e.cart());self.e.local('cancel');self.e.local('confirm checkout');self.assertTrue(self.e.cart());self.e.local('checkout');self.assertIn('DEMO order',self.e.local('confirm checkout'));self.assertFalse(self.e.cart())
 def test_changed(self):
  self.e.local('add milk');self.e.local('checkout');self.e.add(self.e.matches('Bread White 700g')[0]['id']);self.assertIn('changed',self.e.local('confirm checkout'))
 def test_auth(self):
  a=Accounts(Path(self.tmp.name)/'accounts.db');a.register('Test','test@example.com','password123');self.assertTrue(a.login('test@example.com','password123'));self.assertIsNone(a.login('test@example.com','wrong'));a.db.close()
 def test_isolation(self):
  other=s.Engine(2);self.e.local('add milk');self.assertFalse(other.cart());other.conn.close()
 def test_negation(self):self.e.local('add no milk without bread');self.assertFalse(self.e.cart())
 def test_stock(self):
  p=next(p for p in self.e.products if int(p['stock'])==0);self.assertIn('Not enough',self.e.add(p['id'],1))
if __name__=='__main__':unittest.main(verbosity=2)
