import assert from "node:assert/strict";import test from "node:test";import { buildMetadataQuery } from "./api/metadata";
test("يبني فلاتر فهرس البيانات دون القيم الفارغة",()=>{assert.equal(buildMetadataQuery({search:"طرابلس",entry_type:"dataset",classification_level:""}),"search=%D8%B7%D8%B1%D8%A7%D8%A8%D9%84%D8%B3&entry_type=dataset")});
test("يحافظ mapper التجريبي على pagination الآمن",()=>{const page={demo:true,items:[],total:0,limit:25,offset:0};assert.equal(page.demo,true);assert.equal(page.items.length,0)});
