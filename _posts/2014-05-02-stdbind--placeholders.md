---
layout: post
title: "std::bind 与 placeholders"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
一直觉得 placeholder 这种设施和奇妙，竟然可以调换参数顺序 = =。

{% highlight cpp %}
using namespace std;
using namespace std::placeholders

void gao(const string& s, int i) { cout << s << i << endl; }   

int main() {    
    auto f = bind(gao, _2, _1);
    f(1, string("1"));
    return 0; 
}
{% endhighlight %}
<!--more-->

后来去搜了一下实现，有一个简单的 [tut](http://accu.org/index.php/journals/1397)，介绍了 placeholder 实现的基本思路。在此基础上拓展，就是一个可用的 bind 和 placeholder 了。

那真实 stl 中的 bind 和 placeholders 是怎么搞的呢？

来到 include/std/functional
bind 有两种，一种是直接 bind 到 Function 上面，另一种是 bind&lt;R&gt;，也就是显式指定返回类型的 bind。其实只要看一种就可以知晓原理了。

{% highlight cpp %}
  /**
   * @brief Function template for std::bind.
   * @ingroup binders
   */
  template<typename _Func, typename... _BoundArgs>
    inline typename
    _Bind_helper<__is_socketlike<_Func>::value, _Func, _BoundArgs...>::type
    bind(_Func&& __f, _BoundArgs&&... __args)
    {
      typedef _Bind_helper<false, _Func, _BoundArgs...> __helper_type;
      typedef typename __helper_type::__maybe_type __maybe_type;
      typedef typename __helper_type::type __result_type;
      return __result_type(__maybe_type::__do_wrap(std::forward<_Func>(__f)),
                           std::forward<_BoundArgs>(__args)...);
    }
{% endhighlight %}

注意看 bind 返回的类型：
{% highlight cpp %}
_Bind_helper<__is_socketlike<_Func>::value, _Func, _BoundArgs...>::type 
{% endhighlight %}

很奇怪诶，这个 \_\_is\_socketlike 是做什么的呢？
{% highlight cpp %}
  // Trait type used to remove std::bind() from overload set via SFINAE
  // when first argument has integer type, so that std::bind() will
  // not be a better match than ::bind() from the BSD Sockets API.
  template<typename _Tp, typename _Tp2 = typename decay<_Tp>::type>
    using __is_socketlike = __or_<is_integral<_Tp2>, is_enum<_Tp2>>;
{% endhighlight %}

够人性化吧。这是为了防止和 Socket API 里面的 bind 发生重载冲突。
\_\_is\_socketlike 在 \_Tp 为 integral  或者 enum 类型的时候为 true。当 bind 传进来的第一个参数是 function 时，\_\_is\_socketlike 为 false；当 bind 传进来第一个参数是 int 类型时，\_\_is\_socketlike  为 true。

\_Bind\_helper 在第一个模板参数上做了特化。
{% highlight cpp %}
  // Partial specialization for is_socketlike == true, does not define
  // nested type so std::bind() will not participate in overload resolution
  // when the first argument might be a socket file descriptor.
  template<typename _Func, typename... _BoundArgs>
    struct _Bind_helper<true, _Func, _BoundArgs...>
    { };
{% endhighlight %}

当 \_\_is\_socketlike 为 true 时，偏特化的版本里面并没有 ::type，由于 SFINAE，此时 std::bind 不出现在 bind 的重载中。而当 \_\_is\_socketlike 为 false 时，std::bind 才是干活的时候~~

在 bind 中要用到 \_Bind\_helper::\_\_maybe\_type 和 \_\_Bind\_helper::type。在 \_Bind\_helper 中

{% highlight cpp %}
  template<bool _SocketLike, typename _Func, typename... _BoundArgs>
    struct _Bind_helper
    {
      typedef _Maybe_wrap_member_pointer<typename decay<_Func>::type>
        __maybe_type;
      typedef typename __maybe_type::type __func_type;
      typedef _Bind<__func_type(typename decay<_BoundArgs>::type...)> type;
    }; 
{% endhighlight %}

跟到 \_Maybe\_wrap\_member\_pointer 中去。

{% highlight cpp %}
  /**
   * Maps member pointers into instances of _Mem_fn but leaves all
   * other function objects untouched. Used by tr1::bind(). The
   * primary template handles the non--member-pointer case.
   */
  template<typename _Tp>
    struct _Maybe_wrap_member_pointer
    {
      typedef _Tp type;
      static const _Tp&
      __do_wrap(const _Tp& __x)
      { return __x; }
      static _Tp&&
      __do_wrap(_Tp&& __x)
      { return static_cast<_Tp&&>(__x); }
    };
  /**
   * Maps member pointers into instances of _Mem_fn but leaves all
   * other function objects untouched. Used by tr1::bind(). This
   * partial specialization handles the member pointer case.
   */
  template<typename _Tp, typename _Class>
    struct _Maybe_wrap_member_pointer<_Tp _Class::*>
    {
      typedef _Mem_fn<_Tp _Class::*> type;
      static type
      __do_wrap(_Tp _Class::* __pm)
      { return type(__pm); }
    };

  // Specialization needed to prevent "forming reference to void" errors when
  // bind<void>() is called, because argument deduction instantiates
  // _Maybe_wrap_member_pointer<void> outside the immediate context where
  // SFINAE applies.
  template<>
    struct _Maybe_wrap_member_pointer<void>
    {
      typedef void type;
    };
{% endhighlight %}

这里是对 class member function 的情况做封装，在这种情况下，我们需要 \_Mem\_fn 的辅助（之前 std::function 篇有看过 \_Mem\_fn 的实现）。注意到还有 &lt;void&gt; 的特化，来看两种 bind

{% highlight cpp %}
  template<typename _Func, typename... _BoundArgs>
    inline typename
    _Bind_helper<__is_socketlike<_Func>::value, _Func, _BoundArgs...>::type
    bind(_Func&& __f, _BoundArgs&&... __args)

  template<typename _Result, typename _Func, typename... _BoundArgs>
    inline
    typename _Bindres_helper<_Result, _Func, _BoundArgs...>::type
    bind(_Func&& __f, _BoundArgs&&... __args)
{% endhighlight %}

我们显示的使用 std::bind&lt;int(int)&gt; 和 std:bind&lt;int&gt; 的时候，会匹配到哪个函数上呢？如果说 std::bind&lt;int&gt; 匹配到了第一种 bind 上去，根据之前的代码，目前还一切顺利，并没有对 \_Func 做具体的类型检查，会继续往下传。

{% highlight cpp %}
      typedef typename __maybe_type::type __func_type;
      typedef _Bind<__func_type(typename decay<_BoundArgs>::type...)> type;
{% endhighlight %}

可以肯定，\_Bind 里面一定对 \_\_func\_type 做了检查，匹配不上则会 SFINAE，而把匹配的任务交给了 std::bind&lt;R&gt;。
但如果是 std::void 呢? 注意到他会在之前匹配

{% highlight cpp %}
  template<typename _Tp>
    struct _Maybe_wrap_member_pointer
    {
      typedef _Tp type;
      static const _Tp&
      __do_wrap(const _Tp& __x)
      { return __x; }
      static _Tp&&
      __do_wrap(_Tp&& __x)
      { return static_cast<_Tp&&>(__x); }
    };
{% endhighlight %}

int 在这里匹配完全没问题，然而 void ~ Ooops，ref to void，你挂了。这就是 void 特化的原因，将匹配错误延迟给 SFINAE，真妙~

废话了半天，刚才进行到了这里
{% highlight cpp %}
typedef _Bind<__func_type(typename decay<_BoundArgs>::type...)> type;
{% endhighlight %}

跟进到 \_Bind 里面。
{% highlight cpp %}
  /// Type of the function object returned from bind().
  template<typename _Signature>
    struct _Bind;
   template<typename _Functor, typename... _Bound_args>
    class _Bind<_Functor(_Bound_args...)>
    : public _Weak_result_type<_Functor>
{% endhighlight %}

发现 \_Bind 只有一个模板参数封装函数签名，然后特化时进行展开。这应该是为了写着方便的原因吧，is\_bind\_expression 什么的可不想知道有这么多模板参数，只要知道你是 \_Bind 就好了（酱紫应该也是提高编译速度吧~）。

回头看一眼 \_Bind 是在哪构造的？就在 std::bind 里面。
{% highlight cpp %}
      return __result_type(__maybe_type::__do_wrap(std::forward<_Func>(__f)),
                           std::forward<_BoundArgs>(__args)...);
{% endhighlight %}

\_\_result\_type 是刚才的 \_Bind\_helper 搞出的 \_Bind&lt;\_\_func\_type(typename decay&lt;\_BoundArgs&gt;::type...)&gt; （我们要构造这样一个 \_Bind），\_\_do\_wrap 就是刚才的 maybe\_wrap\_member 对 class member function 的封装。

恩，我们可以看 \_Bind 的构造函数了。

{% highlight cpp %}
     public:
      template<typename... _Args>
        explicit _Bind(const _Functor& __f, _Args&&... __args)
        : _M_f(__f), _M_bound_args(std::forward<_Args>(__args)...)
        { }
      template<typename... _Args>
        explicit _Bind(_Functor&& __f, _Args&&... __args)
        : _M_f(std::move(__f)), _M_bound_args(std::forward<_Args>(__args)...)
        { }
      _Bind(const _Bind&) = default;
      _Bind(_Bind&& __b)
      : _M_f(std::move(__b._M_f)), _M_bound_args(std::move(__b._M_bound_args))
      { }
{% endhighlight %}

\_M\_f 应该是存函数指针的，关键在 \_M\_bound\_args。

{% highlight cpp %}
      _Functor _M_f;
      tuple<_Bound_args...> _M_bound_args;
{% endhighlight %}

原来是用 tuple 做的。诶，这么做真的大丈夫？ bind 的时候并没有做 args 和 function 签名的检查，也就是说咱们想怎么干就怎么干，只有在实际 call 的时候做匹配才会出现错误。

那 call 的时候是怎么跟这些 args 关联起来呢。我们来看下 call 的过程吧，也就是 operator() 。
call 有四小类，分别是 unqualified, const, volatile, const volatile。
来看最基础的。

{% highlight cpp %}
      // Call unqualified
      template<typename... _Args, typename _Result
        = decltype( std::declval<_Functor>()(
              _Mu<_Bound_args>()( std::declval<_Bound_args&>(),
                                  std::declval<tuple<_Args...>&>() )... ) )>
        _Result
        operator()(_Args&&... __args)
        {
          return this->__call<_Result>(
              std::forward_as_tuple(std::forward<_Args>(__args)...),
              _Bound_indexes());
        }
{% endhighlight %}
用之前 function 里面的方法，得到了 返回类型 \_Result。令人疑惑的是 \_Mu，他似乎起到了拼接 \_Bound\_args 和刚传入的 args 的作用。

{% highlight cpp %}
_Mu<_Bound_args>()( std::declval<_Bound_args&>(), std::declval<tuple<_Args...>&>() )... 
{% endhighlight %}
按 \_Bound\_args 展开，也就是对于每一个 \_Bound\_args 中的 type 来说，按
{% highlight cpp %}
_Mu<type>()( std::declval<type&>(), std::declval<tuple<_Args...>&>() )
{% endhighlight %}

来看 \_Mu
{% highlight cpp %}
  template<typename _Arg,
           bool _IsBindExp = is_bind_expression<_Arg>::value,
           bool _IsPlaceholder = (is_placeholder<_Arg>::value > 0)>
    class _Mu;
{% endhighlight %}

is\_bind\_expression 显而易见
{% highlight cpp %}
  template<typename _Signature>
    struct is_bind_expression<_Bind<_Signature> >
    : public true_type { };
{% endhighlight %}

对了，还没看过 placeholders 是什么样的
{% highlight cpp %}
  template<int _Num> struct _Placeholder { };

    extern const _Placeholder<1> _1;
    extern const _Placeholder<2> _2;
{% endhighlight %}
没用的占位符你们好。我们继续看 \_Mu。刚才 \_Mu 上调了 operator()。

我们先看最基础的情况。
{% highlight cpp %}
  template<typename _Arg>
    class _Mu<_Arg, false, false>
    {
    public:
      template<typename _Signature> struct result;
      template<typename _CVMu, typename _CVArg, typename _Tuple>
        struct result<_CVMu(_CVArg, _Tuple)>
        {
          typedef typename add_lvalue_reference<_CVArg>::type type;
        };
      // Pick up the cv-qualifiers of the argument
      template<typename _CVArg, typename _Tuple>
        _CVArg&&
        operator()(_CVArg&& __arg, _Tuple&) const volatile
        { return std::forward<_CVArg>(__arg); }
    };
{% endhighlight %}
此时 \_Mu 没有起到任何作用，只是转发而已。（相应的还有一个 reference\_wrapper 的特化）

如果 is\_bind\_expression 是 true 呢？ 诶。。什么时候会出现这种情况，传给 \_Mu 的不都是 \_Bound\_args 么？
卧槽。难道我们可以 f = std::bind(funA, std::bind(funB, 1), 2)，然后再 f("abc", "def") 简直。。不忍直视啊。
{% highlight cpp %}
int a(int en) {
    return en + 1;
}
int b(int en) {
    return en + 1;
}

auto c = std::bind(b, std::bind(a, 1)); 
std:: cout << c();
{% endhighlight %}

{% highlight cpp %}
  /**
   * If the argument is a bind expression, we invoke the underlying
   * function object with the same cv-qualifiers as we are given and
   * pass along all of our arguments (unwrapped). [TR1 3.6.3/5 bullet 2]
   */
  template<typename _Arg>
    class _Mu<_Arg, true, false>
    {
    public:
      template<typename _CVArg, typename... _Args>
        auto
        operator()(_CVArg& __arg,
                   tuple<_Args...>& __tuple) const volatile
        -> decltype(__arg(declval<_Args>()...))
        {
          // Construct an index tuple and forward to __call
          typedef typename _Build_index_tuple<sizeof...(_Args)>::__type
            _Indexes;
          return this->__call(__arg, __tuple, _Indexes());
        }
    private:
      // Invokes the underlying function object __arg by unpacking all
      // of the arguments in the tuple.
      template<typename _CVArg, typename... _Args, std::size_t... _Indexes>
        auto
        __call(_CVArg& __arg, tuple<_Args...>& __tuple,
               const _Index_tuple<_Indexes...>&) const volatile
        -> decltype(__arg(declval<_Args>()...))
        {
          return __arg(std::forward<_Args>(get<_Indexes>(__tuple))...);
        }
    };
{% endhighlight %}

果然。。。继续看下去，placeholder 是怎么搞的。

{% highlight cpp %}
  /**
   * If the argument is a placeholder for the Nth argument, returns
   * a reference to the Nth argument to the bind function object.
   * [TR1 3.6.3/5 bullet 3]
   */
  template<typename _Arg>
    class _Mu<_Arg, false, true>
    {
    public:
      template<typename _Signature> class result;
      template<typename _CVMu, typename _CVArg, typename _Tuple>
        class result<_CVMu(_CVArg, _Tuple)>
        {
          // Add a reference, if it hasn't already been done for us.
          // This allows us to be a little bit sloppy in constructing
          // the tuple that we pass to result_of<...>.
          typedef typename _Safe_tuple_element<(is_placeholder<_Arg>::value
                                                - 1), _Tuple>::type
            __base_type;
        public:
          typedef typename add_rvalue_reference<__base_type>::type type;
        };
      template<typename _Tuple>
        typename result<_Mu(_Arg, _Tuple)>::type
        operator()(const volatile _Arg&, _Tuple& __tuple) const volatile
        {
          return std::forward<typename result<_Mu(_Arg, _Tuple)>::type>(
              ::std::get<(is_placeholder<_Arg>::value - 1)>(__tuple));
        }
    };

{% endhighlight %}
从 placeholder 里面拿到标号，再从 args 的 tuple 里面 get，就拿到了对应的 arg。这就是 placeholder 干活的原理啊。
这里有一个 \_Safe\_tuple\_element，不过感觉用处并不大，只是想出错的时候少爆点 error 。。（4K 吓哭你）。

\_Mu 已经看完，虽然刚才只是从模板参数上引进去的，不过 \_Mu 似乎已经做完了绝大多数事情啊。我们回到 \_Bind::operator()。

{% highlight cpp %}
      // Call unqualified
      template<typename... _Args, typename _Result
        = decltype( std::declval<_Functor>()(
              _Mu<_Bound_args>()( std::declval<_Bound_args&>(),
                                  std::declval<tuple<_Args...>&>() )... ) )>
        _Result
        operator()(_Args&&... __args)
        {
          return this->__call<_Result>(
              std::forward_as_tuple(std::forward<_Args>(__args)...),
              _Bound_indexes());
        }
{% endhighlight %}

在看 \_\_call 之前，还有一个奇怪的 \_Bound\_indexes()。刚才 \_Mu 不是已经可以 work 么，为什么要这个。
看一下 \_\_call

{% highlight cpp %}
      // Call unqualified
      template<typename _Result, typename... _Args, std::size_t... _Indexes>
        _Result
        __call(tuple<_Args...>&& __args, _Index_tuple<_Indexes...>)
        {
          return _M_f(_Mu<_Bound_args>()
                      (get<_Indexes>(_M_bound_args), __args)...);
        }
{% endhighlight %}
是一个很悲催的原因，之前 \_M\_bound\_args 可以通过 ... 做类型展开，然而对于一个 bind 后的 tuple，我们必须用借助辅助工具，让其中的 element 跟着一起展开。get 是选择的方法，而确定 arg 和 element 对应关系的就是这个 \_Index\_tuple，上面的 \_Indexes 就是展开的模板参数。（其实展开就是 0,1,2,3 .....）

来看一下 index 是怎么搞出来的。
{% highlight cpp %}
      typedef typename _Build_index_tuple<sizeof...(_Bound_args)>::__type
        _Bound_indexes;
{% endhighlight %}
那啥，这里的 [sizeof...](http://en.cppreference.com/w/cpp/language/sizeof...) 是 args 的个数。 

吃惊的是 \_Build\_index\_tuple 是在 utility 里面
{% highlight cpp %}
  // Stores a tuple of indices. Used by tuple and pair, and by bind() to
  // extract the elements in a tuple.
  template<size_t... _Indexes>
    struct _Index_tuple
    {
      typedef _Index_tuple<_Indexes..., sizeof...(_Indexes)> __next;
    };
  // Builds an _Index_tuple<0, 1, 2, ..., _Num-1>.
  template<size_t _Num>
    struct _Build_index_tuple
    {
      typedef typename _Build_index_tuple<_Num - 1>::__type::__next __type;
    };
  template<>
    struct _Build_index_tuple<0>
    {
      typedef _Index_tuple<> __type;
    };
{% endhighlight %}

\_Build\_index\_tuple 又一次展现递归的强大属性。我们来看那一下 \_Build\_index\_tuple::type 是怎么解析出来的，以 \_Num == 3 为例。

{% highlight cpp %}
_Build_index_tuple<3>
typedef typename _Build_index_tuple<2>::__type::__next __type;

_Build_index_tuple<2>
typedef typename _Build_index_tuple<1>::__type::__next __type;

_Build_index_tuple<1>
typedef typename _Build_index_tuple<0>::__type::__next __type;

_Build_index_tuple<0>
typedef _Index_tuple<> __type;
{% endhighlight %}

反向递推回去
{% highlight cpp %}
_Build_index_tuple<1>
typedef _Index_tuple<0> __type;

_Build_index_tuple<2>
typedef _Index_tuple<0, 1> __type;

_Build_index_tuple<2>
typedef _Index_tuple<0, 1, 2> __type;
{% endhighlight %}

于是我们构造出来了 \_Index\_tuple&lt;0, 1, 2, ... \_Num - 1&gt; 简直叹为观止。。。。。

### 总结一下
1. \_Build\_index\_tuple 简直是神作，强大的模板。。。
2. bind 通过 \_Mu 模板特化以及模板参数展开实现 placeholder 替换和参数的选择。bind 必须 bind 函数所有的参数，空缺用 placeholder 代替（C++ 木有 partial fun）。
3. \_Mu 做 trait 的时候可不管你 call 的时候给了多少参数（只要给 placeholder 够用了就可以），所以 call bind 的函数如果多传了参数一样编译通过。
4. bind 后的结果 \_Bind 可以转换成 function 么？可以，然而 Bind 并没有提供返回类型和参数类型（\_Weak\_result 这个基类现在还没有被用到），\[del\]function 在接受 \_Functor 时只做 callable 检查，所以任何类型的 \_Bind 都可以被转换成任何类型的 function，take care。\[/del\] 不过在模板实例化的时候，callable 检查会生效，所以跟第三条一样，返回值要 convertable，参数不能少（但可以多）。
然而 lambda 对参数的要求则是严格的，因为 lambda 是通过 struct operator() 实现的喔。

顺便给一下例子～～
{% highlight cpp %}
int b(int en, const char* c) {
    return en + 1;
}
auto d = std::bind(b, std::placeholders::_1, std::placeholders::_2);
std::cout << d(1, "asdf") << std::endl;
// std::cout << d(1) << std::endl; error !
// std::cout << d("asdf", "asdf") << std::endl; error !
std::cout << d(1, "asdf", 13) << std::endl;
std::function<int(int, const char*)> d1 = std::bind(b, std::placeholders::_1, std::placeholders::_2);
std::function<int(int, const char*, int)> d2 = std::bind(b, std::placeholders::_1, std::placeholders::_2);
// std::function<int(int, int)> d3 = std::bind(b, std::placeholders::_1, std::placeholders::_2); error !
{% endhighlight %}

