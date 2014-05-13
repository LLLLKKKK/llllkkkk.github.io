---
layout: post
title: "从 duration 看 user defined literal"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
C++11 引入了 [user defined literal](http://en.cppreference.com/w/cpp/language/user_literal)，干嘛用的呢？继续抄例子：

{% highlight cpp %}
#include <iostream>
 
// used as conversion
constexpr long double operator"" _deg ( long double deg )
{
    return deg*3.141592/180;
}
 
// used with custom type
struct mytype
{
    mytype ( unsigned long long m):m(m){}
    unsigned long long m;
};
mytype operator"" _mytype ( unsigned long long n )
{
    return mytype(n);
}
 
int main(){
    double x = 90.0_deg;
    std::cout << std::fixed << x << '\n';
    mytype y = 123_mytype;
    std::cout << y.m << '\n';
}
{% endhighlight %}

感觉最最重要的是，它方便了定义单位。比如说在程序中定义了 MB，KB 这样几个单位，每一个都是一个类型，酱紫让人很难堪。
1. 一方面声明变量的时候很不自然（complex<double> z1(1, 2)）
2. 必须手工去写转换函数（GB，MB，KB。。。），冤冤转换何时了？。

而现在对于这样两个问题，如果有 user defined literal
1. complex<double> z = 1 + 2i
2. 将 GB，MB 等统一成一个 SIZE 类型，SIZE mem = 4_GB

operator"" 是针对 integer, float, string, character 这四种 literal 定义的，当然你可能在数字里面看到奇奇怪怪的 digit seperator （[N3781](http://www.open-std.org/jtc1/sc22/wg21/docs/papers/2013/n3781.pdf) [N2281](http://www.open-std.org/jtc1/sc22/wg21/docs/papers/2007/n2281.html) ）也就是说我们自己定义的 suffix 之前必须是这四种之一。

operator"" 有以下几种定义方式
{% highlight cpp %}
// 这四种是针对不同类型的
// 从 name 前面拿整形的数字（integer）
decl return operator"" name ( unsigned long long n ) { body }
// 从 name 前面拿浮点型的数字（float）
decl return operator"" name ( long double d ) { body }
// 把 name 前面拿一个 char（ex. 'a'）    （character）
decl return operator"" name ( char_type c ) { body }
// 把 name 前面拿 c-style 字符串，顺便有长度（string）
decl return operator"" name ( const char_type * str, size_t sz ) { body }

// 这两种是针对 integer 和 float 类型，重载匹配顺序递减。
// 把 name 把前面的东西当做 c-style 字符串拿来
decl return operator"" name ( const char* cstr ) { body }
// 把 name 前面的内容用模板参数拿到，一坨一坨的 char
template <char...>decl return operator"" name ( ){ body }
{% endhighlight %}

operator"" 大致就是酱紫，接下来看一个 operator"" 的实际应用，`std::chrono::duration`。duration  是个蛮简单的类，用来表示时间的间隔。（duration 的 operator"" 是 C++14 的内容）

duration 里面有两个模板参数，一个是 _Rep，会作为 duration 内部的成员，是时间的表示类型。另一个是 _Period 接受 ratio 为模板参数，作为数量级的表示。不同 _Period 的 duration 可以通过 duration cast 来做转换。

对 ratio 不熟悉的看[这里](http://llllkkkk.github.io/2014/05/12/stdratio/)

{% highlight cpp %}
    template<typename _Rep, typename _Period = ratio<1>>
      struct duration;

    /// nanoseconds
    typedef duration<int64_t, nano> nanoseconds;

    /// microseconds
    typedef duration<int64_t, micro> microseconds;

    /// milliseconds
    typedef duration<int64_t, milli> milliseconds;

    /// seconds
    typedef duration<int64_t> seconds;

    /// minutes
    typedef duration<int64_t, ratio< 60>> minutes;

    /// hours
    typedef duration<int64_t, ratio<3600>> hours;
{% endhighlight %}

当然本次的重点是 operator""，关键来了。

operator"" 对 `h`，`min`，`s`，`ms`，`us` 等几种，搞懂其中一个其他都是一模一样的。
{% highlight cpp %}
    constexpr chrono::duration<long double, ratio<3600,1>>
    operator""h(long double __hours)
    { return chrono::duration<long double, ratio<3600,1>>{__hours}; }

    template <char... _Digits>
      constexpr typename
      __select_type::_Select_type<__select_int::_Select_int<_Digits...>::value,
                             chrono::hours>::type
      operator""h()
      {
        return __select_type::_Select_type<
                          __select_int::_Select_int<_Digits...>::value,
                          chrono::hours>::value;
      }
{% endhighlight %}

如果是 `1.2h` 这样的浮点型，会直接匹配到上面 `long double` 的 `operator""`。如果是整形则会都送给那个函数模板，为什么整形需要这种特殊处理呢？

{% highlight cpp %}
  inline namespace literals
  {
  inline namespace chrono_literals
  {
    namespace __select_type
    {

      using namespace __parse_int;

      template<unsigned long long _Val, typename _Dur>
        struct _Select_type
        : conditional<
            _Val <= static_cast<unsigned long long>
                      (numeric_limits<typename _Dur::rep>::max()),
            _Dur, void>
        {
          static constexpr typename _Select_type::type
            value{static_cast<typename _Select_type::type>(_Val)};
        };

      template<unsigned long long _Val, typename _Dur>
        constexpr typename _Select_type<_Val, _Dur>::type
        _Select_type<_Val, _Dur>::value;

    } // __select_type
{% endhighlight %}

顺便提一下 [inline namespace](http://www.stroustrup.com/C++11FAQ.html#inline-namespace) 是一个很萌的东西。
`_Select_type` 是用来判断前面的整形会不会溢出 duration 的 rep，如果一切安全就 cast 到 duration 的 rep。注意这里传进来的 `_Val` 是无符号的。。万一是负的怎么办？

来看 `__Select_int` 是怎么 parse 整形数字的，在 `include/bits/parser_number.h`。

{% highlight cpp %}
  template<char... _Digs>
    struct _Select_int
    : _Select_int_base<
        __parse_int::_Parse_int<_Digs...>::value,
        unsigned char,
        unsigned short,
        unsigned int,
        unsigned long,
        unsigned long long
      >
    { };
{% endhighlight %}

parse 的过程在 `_Parse_int`，诶那 `_Select_int_base` 是做什么的？

{% highlight cpp %}
  template<unsigned long long _Val, typename... _Ints>
    struct _Select_int_base;

  template<unsigned long long _Val, typename _IntType, typename... _Ints>
    struct _Select_int_base<_Val, _IntType, _Ints...>
    : integral_constant
      <
        typename conditional
        <
          _Val <= static_cast<unsigned long long>
                    (std::numeric_limits<_IntType>::max()),
          _IntType,
          typename _Select_int_base<_Val, _Ints...>::value_type
        >::type,
        _Val
      >
    { };

  template<unsigned long long _Val>
    struct _Select_int_base<_Val> : integral_constant<unsigned long long, _Val>
    { };
{% endhighlight %}
原来是拿模板递归的勾当来选择能容纳 value 最小的类型，似曾相识的递归在 tuple 里也见过。如果实在撑不住就用 `unsigned long long`。这里依然是无符号的，那就看 parse 的时候怎么处理符号了。

{% highlight cpp %}
  template<char... _Digs>
    struct _Parse_int;
  template<char... _Digs>
    struct _Parse_int<'0', 'b', _Digs...>
    {
      static constexpr unsigned long long
        value{_Number<2U, _Digs...>::value};
    };
// .... 略过一些
  template<char... _Digs>
    struct _Parse_int
    {
      static constexpr unsigned long long
        value{_Number<10U, _Digs...>::value};
    };
{% endhighlight %}

parse number 首先对开头的进制做处理，有 0b，0B，0x，0X，0 这几种，如果没有特殊开头就是 base10，还是没有看到负号。想到这里突然恍然大悟，负号不是跟数字一起 parse 的，而是当做运算符 parse 的，这里拿到的一直是 unsigned 的数字。

{% highlight cpp %}
  template<unsigned _Base, char... _Digs>
    struct _Number
    {
      static constexpr unsigned
        value{_Number_help<_Base, _Power<_Base, _Digs...>::value,
                           _Digs...>::value};
    };

  template<unsigned _Base>
    struct _Number<_Base>
    {
      static constexpr unsigned value{0U};
    };
{% endhighlight %}

接下来又是展现强大的模板能力的时候，这种将字符串转换成数字的练习以前已经不知道碰到过多少次了。

{% highlight cpp %}
  template<unsigned _Base, unsigned _Pow, char _Dig, char... _Digs>
    struct _Number_help
    {
      static constexpr unsigned
        value{_Digit<_Base, _Dig>::valid ?
              _Pow * _Digit<_Base, _Dig>::value
              + _Number_help<_Base, _Pow / _Base, _Digs...>::value :
              _Number_help<_Base, _Pow, _Digs...>::value};
    };

  template<unsigned _Base, unsigned _Pow, char _Dig>
    struct _Number_help<_Base, _Pow, _Dig>
    {
      //static_assert(_Pow == 1U, "power should be one");
      static constexpr unsigned
        value{_Digit<_Base, _Dig>::valid ? _Digit<_Base, _Dig>::value : 0U};
    };
{% endhighlight %}

如果这个 digit 是 valid 的话，就把这一位的 pow 乘上去，加上剩下的 parse 结果。`_Power` 应该是获得当前 `1 * Base^n` 的功能。

{% highlight cpp %}
  template<unsigned _Base, char _Dig, char... _Digs>
    struct _Power_help
    {
      static constexpr unsigned
        value{_Digit<_Base, _Dig>::valid ?
              _Base * _Power_help<_Base, _Digs...>::value :
              _Power_help<_Base, _Digs...>::value};
    };

  template<unsigned _Base, char _Dig>
    struct _Power_help<_Base, _Dig>
    {
      static constexpr unsigned value{_Digit<_Base, _Dig>::valid ? 1U : 0U};
    };

  template<unsigned _Base, char... _Digs>
    struct _Power
    {
      static constexpr unsigned value{_Power_help<_Base, _Digs...>::value};
    };
{% endhighlight %}
不过注意到里面的 value 一直都是 unsigned，这要想让你溢出不是分分钟？ 好吧已经去交了 bug，不知道是不是酱紫（或许出丑了）。

至于 `_Digit` 呢就很简单了，看几个就懂了。

{% highlight cpp %}
  template<unsigned _Base, char _Dig>
    struct _Digit;

  template<unsigned _Base>
    struct _Digit<_Base, '0'>
    {
      static constexpr bool valid{true};
      static constexpr unsigned value{0};
    };

  template<unsigned _Base>
    struct _Digit<_Base, '1'>
    {
      static constexpr bool valid{true};
      static constexpr unsigned value{1};
    };

  template<unsigned _Base>
    struct _Digit<_Base, '2'>
    {
      static_assert(_Base > 2, "invalid digit");
      static constexpr bool valid{true};
      static constexpr unsigned value{2};
    };
// ..... 后面的略
  // Digit separator
  template<unsigned _Base>
    struct _Digit<_Base, '\''>
    {
      static constexpr bool valid{false};
      static constexpr unsigned value{0};
    };
{% endhighlight %}

注意这里是支持单引号的 digit seperator，但是不支持下划线。。。。因为酱紫 operator"" 就挂了。
说到底，用模板参数 parse number 比直接给 unsigned long long 有什么优势呢？。。多了一个 0b prefix 而已，真无聊给跪下了。

说道最后，parse_number 其实并没有起到什么作用，一方面节省空间的类型选择根本没用（因为 duration 上的 `_Rep` 都是固定 `int64_t` 的)，二来还出了溢出 bug。。。