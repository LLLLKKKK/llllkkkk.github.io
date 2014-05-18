---
layout: post
title: "Algorithms 之 heap 系列"
description: ""
category: C++
tags: [C++, STL, code reading, algorithm]
---
heap 是非常基础的数据结构，姥姥书中也有很详尽的介绍。STL 中，我们可以在一段 RandomAccessIterator 上 make\_heap，然后进行 pop\_heap 或者 push\_heap 来加入元素或者删除元素。默认的 heap 操作都是用 operator less 定义的，形成的是最大堆。

首先先来热身，看看 is\_heap 以及 is\_heap\_until。既然 heap 的算法已经非常熟悉了，那么就先来 yy 一下怎么实现的吧。heap 可以看做数组中的二叉树，只要保证 parent 比两个 child 都大就可以了，也就是 comp(parent, child) || comp(parent, child + 1) 为 false。parent 从开头到 range / 2 就可以了，不过要注意 child + 1 这个在边界是否存在。

{% highlight cpp %}
    _Distance
    __is_heap_until(_RandomAccessIterator __first, _Distance __n,
                    _Compare __comp)
    {
      _Distance __parent = 0;
      for (_Distance __child = 1; __child < __n; ++__child)
        {
          if (__comp(__first + __parent, __first + __child))
            return __child;
          if ((__child & 1) == 0)
            ++__parent;
        }
      return __n;
    }
{% endhighlight %}
<!--more-->
这里并没有写两个 comp，而是利用 child 的奇偶性多跑了一次循环。当之前 child 是奇数时，parent 不变 child++，比较右 child；而 child 之前是偶数时，parent++ child++，说明向下进了一层。这时候 for 循环的 check 就充当了对 child + 1 的 check。

先看 push\_heap。last - 1 是对应刚插入的元素，[first, last - 1) 是原来的堆。

{% highlight cpp %}
    inline void
    push_heap(_RandomAccessIterator __first, _RandomAccessIterator __last)
    {
      typedef typename iterator_traits<_RandomAccessIterator>::value_type
          _ValueType;
      typedef typename iterator_traits<_RandomAccessIterator>::difference_type
          _DistanceType;

      _ValueType __value = _GLIBCXX_MOVE(*(__last - 1));
      std::__push_heap(__first, _DistanceType((__last - __first) - 1),
                       _DistanceType(0), _GLIBCXX_MOVE(__value),
                       __gnu_cxx::__ops::__iter_less_val());
    }

    void
    __push_heap(_RandomAccessIterator __first,
                _Distance __holeIndex, _Distance __topIndex, _Tp __value,
                _Compare __comp)
    {
      _Distance __parent = (__holeIndex - 1) / 2;
      while (__holeIndex > __topIndex && __comp(__first + __parent, __value))
        {
          *(__first + __holeIndex) = _GLIBCXX_MOVE(*(__first + __parent));
          __holeIndex = __parent;
          __parent = (__holeIndex - 1) / 2;
        }
      *(__first + __holeIndex) = _GLIBCXX_MOVE(__value);
    }
{% endhighlight %}
也就是在 \_\_holeIndex 和 \_\_topIndex 之间插入一个 \_\_value，让它继续保持堆的性质。需要注意一点的是，以 0 为 index 开始的 heap，两个儿子分别是 2 * parent + 1，2 * parent + 2；而 child 的 parent 则是 (child - 1) / 2。

复杂度呢，At most 2×log(N) comparisons where N=std::distance(first, last)。
那还有 pop\_heap 呢。pop\_heap 会把 heap 最大的元素移到 last - 1 的位置，然后 [first, last - 1)  保持堆的性质。

{% highlight cpp %}
    inline void
    pop_heap(_RandomAccessIterator __first,
             _RandomAccessIterator __last, _Compare __comp)
    {
      if (__last - __first > 1)
        {
          --__last;
          std::__pop_heap(__first, __last, __last,
                          __gnu_cxx::__ops::__iter_comp_iter(__comp));
        }
    }


    inline void
    __pop_heap(_RandomAccessIterator __first, _RandomAccessIterator __last,
               _RandomAccessIterator __result, _Compare __comp)
    {
      typedef typename iterator_traits<_RandomAccessIterator>::value_type
        _ValueType;
      typedef typename iterator_traits<_RandomAccessIterator>::difference_type
        _DistanceType;
      _ValueType __value = _GLIBCXX_MOVE(*__result);
      *__result = _GLIBCXX_MOVE(*__first);
      std::__adjust_heap(__first, _DistanceType(0),
                         _DistanceType(__last - __first),
                         _GLIBCXX_MOVE(__value), __comp);
    }
{% endhighlight %}

原来还有一个 \_\_adjust\_heap。首先把 \_\_result 位置的 value 拿住，然后用 \_\_first 赋值，然后用之前的 \_\_result 的值传给 \_\_adjust\_heap。

{% highlight cpp %}
    __adjust_heap(_RandomAccessIterator __first, _Distance __holeIndex,
                  _Distance __len, _Tp __value, _Compare __comp)
    {
      const _Distance __topIndex = __holeIndex;
      _Distance __secondChild = __holeIndex;
      while (__secondChild < (__len - 1) / 2)
        {
          __secondChild = 2 * (__secondChild + 1);
          if (__comp(__first + __secondChild,
                     __first + (__secondChild - 1)))
            __secondChild--;
          *(__first + __holeIndex) = _GLIBCXX_MOVE(*(__first + __secondChild));
          __holeIndex = __secondChild;
        }
      if ((__len & 1) == 0 && __secondChild == (__len - 2) / 2)
        {
          __secondChild = 2 * (__secondChild + 1);
          *(__first + __holeIndex) = _GLIBCXX_MOVE(*(__first
                                                     + (__secondChild - 1)));
          __holeIndex = __secondChild - 1;
        }
      std::__push_heap(__first, __holeIndex, __topIndex,
                       _GLIBCXX_MOVE(__value),
                       __gnu_cxx::__ops::__iter_comp_val(__comp));
    }

{% endhighlight %}
while 循环在 \_\_secondChild * 2 + 1 &lt; \_\_len 的情况下成立，也就是判断目前情况下 \_\_secondChild 的二儿子是不是存在（&lt; \_\_first + \_\_len)，如果存在就将儿子中比较大的移过来。

而在 while 循环终止时，可能会有 \_\_secondChild * 2 + 2 ==  \_\_len 的情况，也就是最后 \_\_secondChild 是存在左儿子的，要额外做一下判断，就是后面的 if。

最后让人蛋碎的是，这里把 hole 移到最后，再次调用了 \_\_push\_heap。不过标准里有写这里的比较是 At most 2 * log(last - first) comparisons，这里都调用 push\_heap 了，保证不了吧。。。又可以提个 (bug)[https://gcc.gnu.org/bugzilla/show_bug.cgi?id=61217] 去看看了。顺便提一句， libcxx 没有这么做，而是像姥姥书上直接做 percolate down。

再看 make\_heap。（模板参数一律略）make\_heap 实际上就从 n /2 - 0 percolate down。

{% highlight cpp %}
    void
    __make_heap(_RandomAccessIterator __first, _RandomAccessIterator __last,
                _Compare __comp)
    {
      typedef typename iterator_traits<_RandomAccessIterator>::value_type
          _ValueType;
      typedef typename iterator_traits<_RandomAccessIterator>::difference_type
          _DistanceType;
      if (__last - __first < 2)
        return;
      const _DistanceType __len = __last - __first;
      _DistanceType __parent = (__len - 2) / 2;
      while (true)
        {
          _ValueType __value = _GLIBCXX_MOVE(*(__first + __parent));
          std::__adjust_heap(__first, __parent, __len, _GLIBCXX_MOVE(__value),
                             __comp);
          if (__parent == 0)
            return;
          __parent--;
        }
    }
{% endhighlight %}

注意到这里的 parent，是不是应该是 (\_\_len - 1) / 2 呢？不是的，因为这里的 \_\_last 其实应该叫 end。。 所以。。。

最后还生一个 sort\_heap，将 max heap 变成有序的数列，其实蛮简单的。

{% highlight cpp %}
    void
    __sort_heap(_RandomAccessIterator __first, _RandomAccessIterator __last,
                _Compare __comp)
    {
      while (__last - __first > 1)
        {
          --__last;
          std::__pop_heap(__first, __last, __last, __comp);
        }
    }
{% endhighlight %}
经过坚持不懈的 pop\_heap，最大值都到了后面，所以。。酱紫就 sort 完了。这里标准保证 At most N×log(N) comparisons where N=std::distance(first, last)。

### 总结一下~
1. 复习了 heap 数据结构和基本操作
2. is\_heap\_until 的代码里面做奇偶判断来避免child存在判断很巧妙
3. 复杂度分析和正确性证明这里都非常显而易见了其实。
