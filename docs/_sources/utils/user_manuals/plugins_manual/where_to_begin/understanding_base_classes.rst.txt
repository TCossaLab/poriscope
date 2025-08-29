.. _understanding_base_classes:

Understanding Base Classes
==========================

One of the reasons Poriscope is so easy to extend is thanks to base classes.

What Is a Base Class?
---------------------

In object-oriented programming, a base class (also called a superclass) defines common structure and behavior that other classes can inherit from. It's super useful for keeping your code consistent and avoiding repetition.

Imagine a House Blueprint
--------------------------

You're an architect designing all sorts of houses. No matter the style, every house needs a few basic things:

Some things come included, so you don’t need to think about them:

- Walls
- A front door
- A roof

Other things, you do need to decide for yourself:

- Paint color
- Accessories
- Furniture

But the point is, every house still needs all of them.

So, you create a blueprint called ``HousePlan``. It doesn’t build the house — it just tells you what’s absolutely required.

This is exactly what our ``MetaXXXX`` classes do. They are a base structure. On their own, they don’t do anything yet — but they define what must exist for a real analysis tab to work. Some methods come ready to use, and others are left for you to customize — those are marked with ``@abstractmethod``.

Now Let’s Build a Real House
-----------------------------

Let’s say you decide to build a Modern Smart House. It has:

- A front door and a roof (as required by the blueprint)
- But also, solar panels, smart lighting, and an Alexa

You build this house using the ``HousePlan`` blueprint and call it ``SmartHouse``. It follows the rules, but adds its own unique features.

So, in Programmer Talk:

.. code-block:: text

   MetaXXXX = HousePlan → defines what every analysis tab must have (but doesn’t build one)
   CustomXXX = SmartHouse → follows the rules, but creates a fully functional, unique tab
