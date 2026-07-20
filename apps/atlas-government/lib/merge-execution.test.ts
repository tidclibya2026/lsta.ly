import test from"node:test";import assert from"node:assert/strict";import{canExecuteMerge,mapFieldChanges}from"./api/merge-execution";
test("يمنع التنفيذ قبل dry run والتفويض",()=>assert.equal(canExecuteMerge("validated","EXECUTE APPROVED MERGES","data_manager"),false));
test("يتحقق من نص التأكيد والدور",()=>{assert.equal(canExecuteMerge("approved_for_execution","wrong","system_admin"),false);assert.equal(canExecuteMerge("approved_for_execution","EXECUTE APPROVED MERGES","reviewer"),false);assert.equal(canExecuteMerge("approved_for_execution","EXECUTE APPROVED MERGES","data_manager"),true)});
test("ينظف مصفوفة تغييرات الحقول",()=>assert.equal(mapFieldChanges([null,{field:"name_ar"},"bad"]).length,1));
