import unittest
from audit_entity_count_drift import audit
from check_council_refresh_outcome import evaluate
from refresh_health import from_incremental,from_tsv
import json
class MonthlyGuards(unittest.TestCase):
 def test_entity_count_reduction_from_merge_keeps_source_keys(self):
  old=[{'entity_id':'one','source_keys':['A|O']},{'entity_id':'two','source_keys':['B|O']}]
  new=[{'entity_id':'merged','source_keys':['A|O','B|O'],'name':'업체','address':'서울'}]
  d=audit(old,new)
  self.assertEqual(d['delta'],-1)
  self.assertFalse(d['lost_source_keys'])
  self.assertEqual(len(d['merged_previous_entities']),1)
 def test_entity_source_loss_fails(self):
  with self.assertRaises(ValueError):
   audit([{'entity_id':'a','source_keys':['A|O']}],[])
 def test_monthly_full_degraded_and_total_failure(self):
  self.assertTrue(evaluate(from_tsv('icheon\tOK\nansan\tSTALE_OK:DISCOVERY\n'))[0])
  self.assertFalse(evaluate(from_tsv('icheon\tSTALE_OK:DISCOVERY\nansan\tFAILED:INGEST\n'))[0])
 def test_monthly_incremental_degraded_and_total_failure(self):
  def make(a,b):
   return from_incremental(json.dumps({'mode':'incremental','results':[{'source':'icheon','status':a},{'source':'ansan','status':b}]}))
  self.assertTrue(evaluate(make('NO_CHANGE','STALE_OK:INGEST'))[0])
  self.assertFalse(evaluate(make('STALE_OK:INGEST','FAILED:DISCOVERY'))[0])
if __name__=='__main__':unittest.main()
