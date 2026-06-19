# Agent Contract - العقد الموحد للوكلاء

## واجهة الوكيل الموحدة

كل وكيل في النظام يجب أن يلتزم بالواجهة التالية:

### المدخلات (Input)
```yaml
task_id: string (UUID)
description: string
context: object (محدود بحجم السياق)
files: list (ملفات ذات صلة فقط)نEOF
