from django.conf.urls import url
from django.shortcuts import HttpResponse,render,redirect
from django.utils.safestring import mark_safe
from django.urls import reverse
from stark.utils.my_page import Pagination
from django.db.models import Q


class ShowList(object):
    def __init__(self,config_obj,queryset,request):
        self.config_obj = config_obj
        self.queryset = queryset
        self.request = request
        current_page = self.request.GET.get('page',1)
        self.page_obj = Pagination(current_page=current_page,all_count=self.queryset.count(),params=self.request.GET)
        self.page_queryset = self.queryset[self.page_obj.start:self.page_obj.end]

    def get_header(self):
        # 表头展示
        head_list = []
        for head in self.config_obj.get_new_list_display():
            if isinstance(head, str):
                if head == '__str__':
                    val = self.config_obj.model._meta.model_name.upper()
                else:
                    val = self.config_obj.model._meta.get_field(head).verbose_name
            else:
                val = head(self.config_obj, is_header=True)
            head_list.append(val)
        return head_list

    def get_body(self):
        # 表单展示
        body_list = []  # [[obj.title,obj1.price...],[],[]]
        for data in self.page_queryset:
            tmp = []
            for field_or_func in self.config_obj.get_new_list_display():
                if isinstance(field_or_func, str):
                    val = getattr(data, field_or_func)
                    if field_or_func in self.config_obj.list_display_links:
                        _url = self.config_obj.get_reverse_url('edit', data)
                        val = mark_safe("<a href='%s'>%s</a>" % (_url, val))
                else:
                    val = field_or_func(self.config_obj, obj=data)
                tmp.append(val)
            body_list.append(tmp)
        return body_list

    def get_actions(self):
        tmp = []
        # 获取用户定义所有actions
        for action in self.config_obj.actions:  # [patch_init,]
            # 要一个函数名 还要一个中文描述
            tmp.append({
                'name':action.__name__,
                'desc':action.desc
            })
        return tmp  # [{'name':'','desc':''},{},{}]

    def get_filter(self):
        tmp_dict = {}
        for field in self.config_obj.list_filter:  # ['publish','authors']
            tmp_list = []
            rel_model = self.config_obj.model._meta.get_field(field).rel.to
            rel_queryset = rel_model.objects.all()
            filter_value = self.request.GET.get(field)
            import copy
            params1 = copy.deepcopy(self.request.GET)
            if field in params1:
                params1.pop(field)
                s = mark_safe("<a href='?%s'>All</a>"%params1.urlencode())
            else:
                s = mark_safe("<a href=''>All</a>")
            tmp_list.append(s)

            params = copy.deepcopy(self.request.GET)
            for data in rel_queryset:
                params[field] = data.pk
                if filter_value == str(data.pk):
                    s = mark_safe("<a href='?%s' class='active'>%s</a>"%(params.urlencode(),str(data)))
                else:
                    s = mark_safe("<a href='?%s'>%s</a>" % (params.urlencode(), str(data)))
                tmp_list.append(s)
            tmp_dict[field] = tmp_list
        return tmp_dict  # {'publish':[obj1,obj2,obj3...],''}

class ModelStark(object):
    list_display = ['__str__',]
    list_display_links = []
    model_form_class = None
    search_fields = []
    actions = []
    list_filter = []


    def __init__(self, model):
        self.model = model
        self.app_label = self.model._meta.app_label
        self.model_name = self.model._meta.model_name
        self.key_word = ''

    def get_reverse_url(self,type,obj=None):
        if obj:
            _url = reverse('%s_%s_%s'%(self.app_label,self.model_name,type),args=(obj.pk,))
        else:
            _url = reverse('%s_%s_%s'%(self.app_label,self.model_name,type))
        return _url


    def check_col(self,is_header=False,obj=None):
        if is_header:
            return '选择'
        return mark_safe("<input type='checkbox' name='selected_action' value='%s'/>"%obj.pk)

    def edit_col(self,is_header=False,obj=None):
        if is_header:
            return '编辑'
        _url = self.get_reverse_url('edit',obj)
        return mark_safe('<a href="%s">编辑</a>'%_url)

    def delete_col(self,is_header=False,obj=None):
        if is_header:
            return '删除'
        _url = self.get_reverse_url('delete',obj)
        return mark_safe('<a href="%s">删除</a>'%_url)

    def get_new_list_display(self):
        tmp = []
        tmp.append(ModelStark.check_col)
        tmp.extend(self.list_display)
        if not self.list_display_links:
            tmp.append(ModelStark.edit_col)
        tmp.append(ModelStark.delete_col)
        return tmp

    def get_search(self,request,queryset):
        key_word = request.GET.get('q')
        # 2.每次来之前先清空self.key_word
        self.key_word = ''
        if key_word:
            # 1.保存条件
            self.key_word = key_word
            q = Q()
            q.connector = 'or'
            for field in self.search_fields:  # ['title','price']
                q.children.append(('%s__icontains' % field, key_word))
            queryset = queryset.filter(q)
        return queryset

    def get_filter(self,request,queryset):
        q = Q()
        for filter_field in self.list_filter:  # ['publish','authors']
            if filter_field in request.GET:
                filter_val = request.GET.get(filter_field)
                q.children.append((filter_field, filter_val))
        queryset = queryset.filter(q)
        return queryset

    def list_view(self, request):
        # action功能
        if request.method == 'POST':
            action = request.POST.get('action')
            if action:
                pk_list = request.POST.getlist('selected_action')
                queryset = self.model.objects.filter(pk__in=pk_list)
                real_action = getattr(self,action)
                real_action(request,queryset)

        queryset = self.model.objects.all()
        # search功能
        queryset = self.get_search(request,queryset)
        # filter功能
        queryset = self.get_filter(request,queryset)

        show_obj = ShowList(self,queryset,request)
        url = self.get_reverse_url('add')
        return render(request,'stark/list_view.html',locals())


    def get_model_form_class(self):
        if self.model_form_class:
            return self.model_form_class
        from django.forms import ModelForm
        class ModelFormClass(ModelForm):
            class Meta:
                model = self.model
                fields = "__all__"
        return ModelFormClass

    def add_view(self, request):
        model_form_class = self.get_model_form_class()
        model_form_obj = model_form_class()
        if request.method == 'POST':
            model_form_obj = model_form_class(request.POST)
            pop_back_id = request.GET.get('pop_back_id')
            if model_form_obj.is_valid():
                obj = model_form_obj.save()
                if pop_back_id:
                    pk = obj.pk
                    text = str(obj)
                    return render(request,'stark/pop.html',locals())
                return redirect(self.get_reverse_url('list'))
        from django.forms.models import ModelChoiceField
        for form_obj in model_form_obj:
            if isinstance(form_obj.field,ModelChoiceField):
                form_obj.is_pop = True
                rel_model = self.model._meta.get_field(form_obj.name).rel.to
                rel_app_label = rel_model._meta.app_label
                rel_model_name = rel_model._meta.model_name
                url = reverse('%s_%s_add'%(rel_app_label,rel_model_name))
                url = url + '?pop_back_id=' + form_obj.auto_id
                form_obj.url = url
        return render(request,'stark/add.html',locals())

    def edit_view(self, request, id):
        model_form_class = self.get_model_form_class()
        edit_obj = self.model.objects.filter(pk=id).first()
        model_form_obj = model_form_class(instance=edit_obj)
        if request.method ==  "POST":
            model_form_obj = model_form_class(request.POST,instance=edit_obj)
            if model_form_obj.is_valid():
                model_form_obj.save()
                return redirect(self.get_reverse_url('list'))
        return render(request,'stark/edit.html',locals())

    def delete_view(self, request, id):
        self.model.objects.filter(pk=id).delete()
        return redirect(self.get_reverse_url('list'))

    @property
    def urls(self):
        # 模型表所在的应用名/模型表名/操作方法
        tmp = [
            url(r'^$', self.list_view,name='%s_%s_list'%(self.app_label,self.model_name)),
            url(r'^add/', self.add_view,name='%s_%s_add'%(self.app_label,self.model_name)),
            url(r'^edit/(\d+)/', self.edit_view,name='%s_%s_edit'%(self.app_label,self.model_name)),
            url(r'^delete/(\d+)/', self.delete_view,name='%s_%s_delete'%(self.app_label,self.model_name))
        ]
        return tmp, None, None


class StarkSite(object):
    def __init__(self, name='admin'):
        self._registry = {}  # model_class class -> admin_class instance

    def register(self, model, admin_class=None, **options):
        if not admin_class:
            admin_class = ModelStark
        # Instantiate the admin class to save in the registry
        self._registry[model] = admin_class(model)

    def test(self, request):
        return HttpResponse('test')

    def get_urls(self):
        tmp = []
        for model_class, config_obj in self._registry.items():
            app_label = model_class._meta.app_label
            model_name = model_class._meta.model_name
            tmp.append(
                url(r'^%s/%s/' % (app_label, model_name), config_obj.urls)
            )
        return tmp

    @property
    def urls(self):
        return self.get_urls(), None, None


site = StarkSite()

