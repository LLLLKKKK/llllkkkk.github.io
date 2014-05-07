---
layout: post
title: "简析 std::function 实现原理"
description: "解析 STL 中 std::function 的源码"
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}

本篇基于 libstdc++v3，在线代码可以到 [libstdc++](http://gcc.gnu.org/onlinedocs/libstdc++/latest-doxygen/) 上面看，或者直接在自己机器上看（/usr/include/c++/4.....）。不做特殊说明的话，代码都是源自 bits/stl\_functional.h，如果是老版本的有的代码在 functional 。当然老版本和新版本的行号是不一样的。


一元和二元的函数实现非常简单，在  bits/stl\_function.h 中


{% highlight cpp %}
  template<typename _Arg, typename _Result>
    struct unary_function
    {
      /// @c argument_type is the type of the argument
      typedef _Arg argument_type;
      /// @c result_type is the return type
      typedef _Result result_type;
    };
  /**
   * This is one of the @link functors functor base classes@endlink.
   */
  template<typename _Arg1, typename _Arg2, typename _Result>
    struct binary_function
    {
      /// @c first_argument_type is the type of the first argument
      typedef _Arg1 first_argument_type;
      /// @c second_argument_type is the type of the second argument
      typedef _Arg2 second_argument_type;
      /// @c result_type is the return type
      typedef _Result result_type;
    };
{% endhighlight %}


最简单的例子： algorithm 里的 plus, minus 等 functor


{% highlight cpp %}
  template<typename _Tp>
    struct plus : public binary_function<_Tp, _Tp, _Tp>
    {
      _Tp
      operator()(const _Tp& __x, const _Tp& __y) const
      { return __x + __y; }
    };
  /// One of the @link logical_functors Boolean operations functors@endlink.
  template<typename _Tp>
    struct logical_not : public unary_function<_Tp, bool>
    {
      bool
      operator()(const _Tp& __x) const
      { return !__x; }
    };
  /** @} */
{% endhighlight %}

<!--more-->

其实就是一个有 operator() 的 struct
在目前的 libstdc++v3 中，还有这样的内容：


{% highlight cpp %}
#if __cplusplus > 201103L
template<typename _Tp = void>
struct plus;
......
#endif
{% endhighlight %}


也就是允许 plus&lt;void&gt; 的存在。（我没读过标准我也布吉岛为什么） 
而如果没有这个的话，ref void 会在模板实例化时报错。


\_Maybe\_unary\_or\_binary\_function 算是对 function 实现的特化。
分别在二元和一元函数时特化成 unary\_function 和 binary\_function


line 495
{% highlight cpp %}
template<typename _Res, typename... _ArgTypes>
struct _Maybe_unary_or_binary_function { };


template<typename _Res, typename _T1>
struct _Maybe_unary_or_binary_function<_Res, _T1>
: std::unary_function<_T1, _Res> { };


template<typename _Res, typename _T1, typename _T2>
struct _Maybe_unary_or_binary_function<_Res, _T1, _T2>
: std::binary_function<_T1, _T2, _Res> { };
{% endhighlight %}


然后由 function 做 private 继承


function:


{% highlight cpp %}
template<typename _Res, typename... _ArgTypes>
  class function<_Res(_ArgTypes...)>
  : public _Maybe_unary_or_binary_function<_Res, _ArgTypes...>,
  private _Function_base
{% endhighlight %}


当然一路上我们可以学习一下库里怎么写 c++ 的比如：


{% highlight cpp %}
function&
  operator=(function&& __x)
 {
  function(std::move(__x)).swap(*this);
  return *this;
  }
{% endhighlight %}


看到 function::swap ， 可以发现他有三个关键的成员：


{% highlight cpp %}
void swap(function& __x)
  {
  std::swap(_M_functor, __x._M_functor);
  std::swap(_M_manager, __x._M_manager);
  std::swap(_M_invoker, __x._M_invoker);
  }
{% endhighlight %}


其中 \_M\_invoker 也就是 function 本身的成员，就是那个函数指针~~~
{% highlight cpp %}
typedef _Res (*_Invoker_type)(const _Any_data&, _ArgTypes...);
{% endhighlight %}


{% highlight cpp %}
_Invoker_type _M_invoker;
{% endhighlight %}


而 manager 和 functor 则是基类 \_Fucntion\_base 的成员


关键步骤在这里： operator()


{% highlight cpp %}
template<typename _Res, typename... _ArgTypes>
  _Res
  function<_Res(_ArgTypes...)>::
  operator()(_ArgTypes... __args) const
  {
  if (_M_empty())
  __throw_bad_function_call();
  return _M_invoker(_M_functor, std::forward<_ArgTypes>(__args)...);
  }
{% endhighlight %}


大概猜一下，\_M\_functor 是要绑在 class 成员函数上的 this 指针，但是如果这只是一个全局函数而不是某个 class 的成员呢？ 可能猜的并不对。
我们有必要看一下 \_M\_functor \_M\_invoker 是怎么进行初始化的


copy 的时候, \_M\_manager 竟然还要做一些奇奇怪怪的事情~


{% highlight cpp %}
   template<typename _Res, typename... _ArgTypes>
  function<_Res(_ArgTypes...)>::
  function(const function& __x)
  : _Function_base()
  {
  if (static_cast<bool>(__x))
  {
  _M_invoker = __x._M_invoker;
  _M_manager = __x._M_manager;
  __x._M_manager(_M_functor, __x._M_functor, __clone_functor);
  }
  }
{% endhighlight %}


看来 \_M\_manger 里面还有很多黑魔法，留着慢慢看。
我们先来关注一下 function 是怎么造出来的，然后一路跟下去好了~


{% highlight cpp %}
template<typename _Res, typename... _ArgTypes>
template<typename _Functor, typename>
function<_Res(_ArgTypes...)>::
function(_Functor __f)
: _Function_base()
{
typedef _Function_handler<_Signature_type, _Functor> _My_handler;


if (_My_handler::_M_not_empty_function(__f))
{
_My_handler::_M_init_functor(_M_functor, std::move(__f));
_M_invoker = &_My_handler::_M_invoke;
_M_manager = &_My_handler::_M_manager;
}
}
{% endhighlight %}


关键来了，这就是从一个正常的“函数”（或者说函数指针） 构造出 std::function 的过程。当然，我们可以往里面加 puts 再编译验证一下，答案是肯定的。


function(\_functor \_\_f) 的函数声明如下：


{% highlight cpp %}
template<typename _Functor,
typename = _Requires<_Callable<_Functor>, void>>
 function(_Functor);
{% endhighlight %}


问题又变得有些复杂，我们来看 \_Requires 和 \_Callable 的定义，就在 function 类的开头
模板看起来很头疼，不过感觉是对 \_Functor 类型做检查，然后 enable\_if 相应的 Functor 类型的构造函数


{% highlight cpp %}
using _Invoke = decltype(__callable_functor(std::declval<_Functor&>())
                           (std::declval<_ArgTypes>()...) );
template<typename _Functor>
using _Callable = __check_func_return_type<_Invoke<_Functor>, _Res>;


template<typename _Cond, typename _Tp>
using _Requires = typename enable_if<_Cond::value, _Tp>::type;
{% endhighlight %}


从外向内开始，\_Requires 的作用是如果 \_Callable&lt;\_Functor&gt;::value 是 true，则 \_Require&lt;..&gt; 为 void 类型，模板正常匹配，提供对应 \_Functor 类型的构造函数；否则 SFINAE （奇妙的 SFINAE），那么这个 \_Functor 类型的构造函数不存在。
     
而 \_Callable 则会做具体类型检查，其中 \_\_check\_func\_return\_type 的定义也在这个文件中：


{% highlight cpp %}
  template<typename _From, typename _To>
    using __check_func_return_type
      = __or_<is_void<_To>, is_convertible<_From, _To>>;
{% endhighlight %}


作用是是检查函数本身的返回值时候可以被转换成我们定义的function的返回值。
is\_void is\_convertible \_\_or\_ 都是 type\_traits 中的内容（除了\_\_or\_ 其他两个都是 std 中的）


那么检查是否可以被调用的任务就落在 \_Invoke 身上了。可以看到 decltype 里面“发生了”函数调用，想在编译时期获得这个函数返回类型（当然，如果\_Functor不是函数，这时候就挂掉了）
这里出现了一个 std::declval 会给类型加上ref，是为了避免参数类型 \_ArgTypes 中存在没有默认构造函数的类型，导致这一步函数调用在编译期出错。


{% highlight cpp %}
 template<typename _Functor>
inline _Functor&
__callable_functor(_Functor& __f)
{ return __f; }
 template<typename _Member, typename _Class>
inline _Mem_fn<_Member _Class::*>
__callable_functor(_Member _Class::* &__p)
{ return std::mem_fn(__p); }
{% endhighlight %}
。。 还有一些重载略


其实 \_\_callable\_functor 只是起到了一个转换的作用，将不能直接call的（class member function）转换成可以直接上的~ 看来前面是猜错了，\_Any\_data 并不是用来处理 class member func 的。


都看到这里了，顺便看看 std::mem\_fn 是怎么做的吧~


{% highlight cpp %}
template<typename _Tp, typename _Class>
inline _Mem_fn<_Tp _Class::*>
mem_fn(_Tp _Class::* __pm) noexcept
{
return _Mem_fn<_Tp _Class::*>(__pm);
}
{% endhighlight %}


好吧，原来他什么都没有做，只是对 \_Mem\_fn 的 wrapper，那我们看一下 \_Mem\_fn 。


{% highlight cpp %}
template<typename _MemberPointer>
class _Mem_fn;
template<typename _Tp, typename _Class>
_Mem_fn<_Tp _Class::*>
mem_fn(_Tp _Class::*) noexcept;
{% endhighlight %}


是不是有些失望，我们继续往下看。
来看最简单的一个 \_Mem\_fn （mem\_fn对应有 const, volatile 等等各种重载，所以 \_Mem\_fn 也相应的有各种奇奇怪怪的类型）


{% highlight cpp %}
  template<typename _Res, typename _Class, typename... _ArgTypes>
class _Mem_fn<_Res (_Class::*)(_ArgTypes...)>
: public _Maybe_unary_or_binary_function<_Res, _Class*, _ArgTypes...>
{% endhighlight %}


他再一次继承了 \_Maybe\_unary\_or\_binary\_function 这货，到底有什么用呢？
\= \= 其实看了半天我也没想通为什么要做这个继承。。。先不管他


其中有一个成员
{% highlight cpp %}
typedef _Res (_Class::*_Functor)(_ArgTypes...);


  private:
  _Functor __pmf;
{% endhighlight %}
也就是函数的指针。


那是怎样做 call 的呢，还是 operator()


{% highlight cpp %}
 // Handle objects
template<typename... _Args, typename _Req = _RequireValidArgs<_Args...>>
_Res
operator()(_Class& __object, _Args&&... __args) const
{ return (__object.*__pmf)(std::forward<_Args>(__args)...); }
{% endhighlight %}


其实就是做了一层代理而已，拿到对象之后，利用函数指针调用函数。
而且对于 &&, pointer, smart pointer， ref wrapper 都有做对应处理


{% highlight cpp %}
  // Handle pointers
template<typename... _Args, typename _Req = _RequireValidArgs<_Args...>>
_Res
operator()(_Class* __object, _Args&&... __args) const
{ return (__object->*__pmf)(std::forward<_Args>(__args)...); }


// Handle smart pointers, references and pointers to derived
template<typename _Tp, typename... _Args,
typename _Req = _RequireValidArgs2<_Tp, _Args...>>
_Res
operator()(_Tp&& __object, _Args&&... __args) const
{
return _M_call(std::forward<_Tp>(__object), &__object,
std::forward<_Args>(__args)...);
}


template<typename _Tp, typename... _Args,
typename _Req = _RequireValidArgs3<_Tp, _Args...>>
_Res
operator()(reference_wrapper<_Tp> __ref, _Args&&... __args) const
{ return operator()(__ref.get(), std::forward<_Args>(__args)...); }
{% endhighlight %}


关于 mem\_fn 就说这么多。中间的 \_RequireValidArg 的作用是进行一系列类型检查（奇妙的模板）。
对应定义都在 \_Mem\_fn 类内。


好的！ 绕了大半天，我们终于可以回到 function(\_Functor) 这个构造函数了。


{% highlight cpp %}
typedef _Function_handler<_Signature_type, _Functor> _My_handler;


if (_My_handler::_M_not_empty_function(__f))
{
_My_handler::_M_init_functor(_M_functor, std::move(__f));
_M_invoker = &_My_handler::_M_invoke;
_M_manager = &_My_handler::_M_manager;
}
{% endhighlight %}


我们遇到了 \_Function\_handler， \_M\_invoker 和 \_M\_manager 都是从 \_My\_handler 里面拿到的。


{% highlight cpp %}
 typedef _Res _Signature_type(_ArgTypes...);
{% endhighlight %}


sginature type 也就是函数签名类型。


来看 \_Function\_handler


{% highlight cpp %} 
template<typename _Res, typename _Functor, typename... _ArgTypes>
class _Function_handler<_Res(_ArgTypes...), _Functor>
: public _Function_base::_Base_manager<_Functor>
{% endhighlight %}


真是变态啊，它又继承了 \_Function\_base::\_Base\_manager。
既然刚才都是在调用静态方法，那我们就直接看函数


\_M\_not\_empty\_function 实际上是 \_Function\_base::\_Base\_manager 中的静态成员，有几个重载，就是判断函数是不是 null。


{% highlight cpp %}
 template<typename _Signature>
static bool
_M_not_empty_function(const function<_Signature>& __f)
{ return static_cast<bool>(__f); }
{% endhighlight %}


继续看 \_My\_handler::\_M\_init\_functor，public 的方法转发给了 private 做处理。


{% highlight cpp %}
 static void
_M_init_functor(_Any_data& __functor, _Functor&& __f)
{ _M_init_functor(__functor, std::move(__f), _Local_storage()); }
{% endhighlight %}


\_Any\_data 我们一直没有看，不过根据之前的猜想他应该是 class 的一个实例什么的，然后可以在他身上掉 \_M\_invoker。


{% highlight cpp %}
 union _Any_data
{
void* _M_access() { return &_M_pod_data[0]; }
const void* _M_access() const { return &_M_pod_data[0]; }


template<typename _Tp>
_Tp&
_M_access()
{ return *static_cast<_Tp*>(_M_access()); }


template<typename _Tp>
const _Tp&
_M_access() const
{ return *static_cast<const _Tp*>(_M_access()); }


_Nocopy_types _M_unused;
char _M_pod_data[sizeof(_Nocopy_types)];
};
{% endhighlight %}


好吧 \_Any\_data 真的只是 \_Any\_data。 里面可以扔任何东西，那么他到底有什么用呢？
 \_M\_pod\_data 是 sizeof(\_Nocopy\_types)


{% highlight cpp %}
 union _Nocopy_types
{
void* _M_object;
const void* _M_const_object;
void (*_M_function_pointer)();
void (_Undefined_class::*_M_member_pointer)();
};
{% endhighlight %}


也就是一个 pointer 的大小。不过具体用途我们还不清楚，接着看。


刚才还有一个 \_Local\_storage。


{% highlight cpp %}
typedef integral_constant<bool, __stored_locally> _Local_storage;
{% endhighlight %}


定义了一个 bool 常量，那这个\_\_stored\_locally 是做什么的呢。


{% highlight cpp %}
static const bool __stored_locally =
(__is_location_invariant<_Functor>::value
&& sizeof(_Functor) <= _M_max_size
&& __alignof__(_Functor) <= _M_max_align
&& (_M_max_align % __alignof__(_Functor) == 0));
{% endhighlight %}


似乎和 mem layout 开始扯上关系了。慢慢来看~


首先判断 \_Functor 是不是一个指针。


{% highlight cpp %}
 template<typename _Tp>
struct __is_location_invariant
: integral_constant<bool, (is_pointer<_Tp>::value
|| is_member_pointer<_Tp>::value)>
{ };
{% endhighlight %}


然后进一步验证，这货的 size 肯定 &lt;\= pointer。


{% highlight cpp %}
&& sizeof(_Functor) <= _M_max_size


static const std::size_t _M_max_size = sizeof(_Nocopy_types);
{% endhighlight %}


\_\_alignof\_\_ 是 gcc 的扩展。


{% highlight cpp %}
&& __alignof__(_Functor) <= _M_max_align
&& (_M_max_align % __alignof__(_Functor) == 0));


static const std::size_t _M_max_align = __alignof__(_Nocopy_types);
{% endhighlight %}


一时半会看的有点摸不着头脑，这些判断是在做什么？ 暂时扔下继续往下看。


{% highlight cpp %}
 private:
static void
_M_init_functor(_Any_data& __functor, _Functor&& __f, true_type)
{ new (__functor._M_access()) _Functor(std::move(__f)); }


static void
_M_init_functor(_Any_data& __functor, _Functor&& __f, false_type)
{ __functor._M_access<_Functor*>() = new _Functor(std::move(__f)); }
};
{% endhighlight %}


原来是对应 \_Local\_storage 的 true 或者 false 进行不同的 new 操作。也就是说，看 \_Functor 在
是不是能再 \_Any\_data 中存下，如果太大则 new 出来一个，\_Any\_data 只存指针。


不过真的会太大么？函数不都是指针么？no，还有 lambda 表达式~ lambda 表达式似乎是通过 struct 来实现
capture 傻傻的，这里我们先不管他。


既然有 new 了，看来 manager， swap 什么的确实是必要的~ 继续往下看。


{% highlight cpp %}
_M_invoker = &_My_handler::_M_invoke;
_M_manager = &_My_handler::_M_manager;
{% endhighlight %}


这实际上是两个函数指针。具体是哪个函数呢？注意到 \_Function\_handler 实际上是有多个模板重载的


{% highlight cpp %}
template<typename _Res, typename _Functor, typename... _ArgTypes>
class _Function_handler<_Res(_ArgTypes...), _Functor>
: public _Function_base::_Base_manager<_Functor>


 template<typename _Res, typename _Functor, typename... _ArgTypes>
class _Function_handler<_Res(_ArgTypes...), reference_wrapper<_Functor> >
: public _Function_base::_Ref_manager<_Functor>


 template<typename _Class, typename _Member, typename _Res,
typename... _ArgTypes>
class _Function_handler<_Res(_ArgTypes...), _Member _Class::*>
: public _Function_handler<void(_ArgTypes...), _Member _Class::*>
{% endhighlight %}


分别处理 基本情况， reference wrapper，和 class member 等情况。
正因为存在多种情况，所以在 copy, swap 的时候 \_M\_invoke, \_M\_manager 等等都要有相应的变化。


我们先考虑最简单的基本情况。


{% highlight cpp %}
 template<typename _Res, typename _Functor, typename... _ArgTypes>
class _Function_handler<_Res(_ArgTypes...), _Functor>
: public _Function_base::_Base_manager<_Functor>
{
typedef _Function_base::_Base_manager<_Functor> _Base;


public:
static _Res
_M_invoke(const _Any_data& __functor, _ArgTypes... __args)
{
return (*_Base::_M_get_pointer(__functor))(
std::forward<_ArgTypes>(__args)...);
}
};
{% endhighlight %}


\_M\_invoke 又是一层代理，好吧，让我们来看 \_Base\_manager 里面到底在做什么吧。不过可以猜的到，
他应该是根据之前 new 的情况来取这个 pointer 。


{% highlight cpp %}
 // Retrieve a pointer to the function object
static _Functor*
_M_get_pointer(const _Any_data& __source)
{
const _Functor* __ptr =
__stored_locally? std::__addressof(__source._M_access<_Functor>())
/* have stored a pointer */ : __source._M_access<_Functor*>();
return const_cast<_Functor*>(__ptr);
}
{% endhighlight %}


果然不出所料。


接下来看 \_M\_manager


{% highlight cpp %}
 typedef bool (*_Manager_type)(_Any_data&, const _Any_data&, _Manager_operation);
{% endhighlight %}


这是 \_Function\_base 里面对 \_M\_manger 的类型定义。


{% highlight cpp %}
 static bool
_M_manager(_Any_data& __dest, const _Any_data& __source,
_Manager_operation __op)
{
  switch (__op)
{
#ifdef __GXX_RTTI
case __get_type_info:
__dest._M_access<const type_info*>() = &typeid(_Functor);
break;
#endif
case __get_functor_ptr:
__dest._M_access<_Functor*>() = _M_get_pointer(__source);
break;


case __clone_functor:
_M_clone(__dest, __source, _Local_storage());
break;


case __destroy_functor:
_M_destroy(__dest, _Local_storage());
break;
}
return false;
}
{% endhighlight %}


可以看出，\_M\_manager 是根据不同的 operation 对 \_Any\_Data 进行不同操作。还是前面怎么 new 的问题。具体就不仔细分析了，道理和之前 \_M\_init\_functor 都是一样的~


至此，最基本的 std::function 分析已经结束了。略去了 reference wrapper, class member, 还有 cv-qualifier 的一些情况。


### 总结一下：


* function 继承自 \_Function\_base。
*  \_M\_invoke 是 function 的成员，一个函数指针，指向具体的 \_Function\_base::\_Base\_manager::\_M\_invoke 函数（存在 reference wrapper, class member func 等情况）。外界调用 operator() 会转发给 \_M\_invoke，\_M\_invoke 会转发给 \_Function\_base::\_M\_functor。 
*  \_M\_functor 是 \_Function\_base 的成员，\_Any\_data 类型，存放函数指针（或者其他承载函数的东西）。
*  \_M\_Manager 是 \_Function\_base 成员，函数指针，针对 \_M\_functor 的具体内存的分配情况，\_M\_manager 指向相应的管理函数 \_Function\_base::\_Base\_manager::\_M\_Manager )
*  \_Maybe\_unary\_or\_binary\_function 是在为 function operator=(\_Maybe\_unary\_or\_binary\_function) 做准备的啊~ （当 unary 和 binary 赋值给 function）

### 题外话：


*  静态用模板匹配确定类型，然后用函数指针做多态 （\_M\_manager, \_M\_invoke）。也算是学到了新方法~
*  顺便提一下 reference\_wrapper，其实就是一个 pointer wrapper，包着一个指针，实现比较简单。
*  如果是 virtual function 怎么破呢？ 想一下 mem\_fn 怎么做的就明白了。
