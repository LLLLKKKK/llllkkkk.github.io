---
layout: post
title: "containers，先从 container adaptor 说起"
description: ""
category: C++
tags: [C++, STL, code reading]
---
{% include JB/setup %}
STL 中的 container 应该是最最常用的东西了。
​
container adapter，也就是包着 container 的 container。有 queue 和 stack （以及 priority\_queue） 。

container adapter 里面基本没什么实质性内容，把外界的操作转发给里面的 container。

先来 queue。

include/std/stl\_queue.h
{% highlight cpp %}
  template<typename _Tp, typename _Sequence = deque<_Tp> >
    class queue
{% endhighlight %}

<!--more-->
queue 对 container 的要求是 SequenceContainer （Concept），而且要提供 back(), front(), push\_back() pop\_front() 这四个函数。目前满足要求的有 std::deque 和 std::list，默认情况下是 deque。

顺便提一下，deque 的内存布局非常。。奇妙，以后再写 deque。

{% highlight cpp %}
      // concept requirements
      typedef typename _Sequence::value_type _Sequence_value_type;
      __glibcxx_class_requires(_Tp, _SGIAssignableConcept)
      __glibcxx_class_requires(_Sequence, _FrontInsertionSequenceConcept)
      __glibcxx_class_requires(_Sequence, _BackInsertionSequenceConcept)
      __glibcxx_class_requires2(_Tp, _Sequence_value_type, _SameTypeConcept)
{% endhighlight %}
class queue 里面上来是先对 concept 做检查。至于什么是 concept 这里有一片不错的介绍 http://blog.csdn.net/pongba/article/details/1726031 。然而现在 gcc 并没有实现 concept，目前的 concept check 还是通过模板匹配酱紫实现的。所以说虽然能查出来错，但对诊断用处不大（4K 的错误让你明白）。

concept check 相关功能在 include/bits/concept\_check.h 和 include/bits/boost\_concept\_check.h 中，如果想开启的话请先 #define \_GLIBCXX\_CONCEPT\_CHECKS。

{% highlight cpp %}
    public:
      typedef typename _Sequence::value_type value_type;
      typedef typename _Sequence::reference reference;
      typedef typename _Sequence::const_reference const_reference;
      typedef typename _Sequence::size_type size_type;
      typedef _Sequence container_type;
{% endhighlight %}

接下来就是标准里面要求的一些类型定义。比较囧rz 的是下面这段

{% highlight cpp %}
    protected:
      /**
       * 'c' is the underlying container. Maintainers wondering why
       * this isn't uglified as per style guidelines should note that
       * this name is specified in the standard, [23.2.3.1]. (Why?
       * Presumably for the same reason that it's protected instead
       * of private: to allow derivation. But none of the other
       * containers allow for derivation. Odd.)
       */
      _Sequence c;
{% endhighlight %}

好吧，谁会去继承呢？

接下来就是正文了
{% highlight cpp %}
    public:
#if __cplusplus < 201103L
      explicit
      queue(const _Sequence& __c = _Sequence())
      : c(__c) { }
#else
      explicit
      queue(const _Sequence& __c)
      : c(__c) { }
      explicit
      queue(_Sequence&& __c = _Sequence())
      : c(std::move(__c)) { }
#endif
{% endhighlight %}

{% highlight cpp %}
      bool
      empty() const
      { return c.empty(); }

      size_type
      size() const
      { return c.size(); }

      reference
      front()
      {
        __glibcxx_requires_nonempty();
        return c.front();
      }
{% endhighlight %}

接下来看到的基本上都是这种内容了。。。没啥意思。
之前好像一直没说过 swap，这里补一下好了。

{% highlight cpp %}
      void
      swap(queue& __q)
      noexcept(noexcept(swap(c, __q.c)))
      {
        using std::swap;
        swap(c, __q.c);
      }
{% endhighlight %}

然后再外面会有
{% highlight cpp %}
  template<typename _Tp, typename _Seq>
    inline void
    swap(queue<_Tp, _Seq>& __x, queue<_Tp, _Seq>& __y)
    noexcept(noexcept(__x.swap(__y)))
    { __x.swap(__y); }
{% endhighlight %}

真是无聊 = = 我们来看下 priority\_queue 

{% highlight cpp %}
  template<typename _Tp, typename _Sequence = vector<_Tp>,
           typename _Compare = less<typename _Sequence::value_type> >
{% endhighlight %}

priority\_queue 是利用 make\_heap, pop\_heap, push\_heap 维持的最大堆（priority 大的在前）
其实也没什么值得一提的 = = 

stack 呢。。。也就那样吧

{% highlight cpp %}
  template<typename _Tp, typename _Sequence = deque<_Tp> >
    class stack
{% endhighlight %}

这篇就这么烂掉好了，其他 container 的内容自然会多。