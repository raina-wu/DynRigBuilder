

# DynRigBuilder
DynRigBuilder builds a nHair-based dynamic rig in Maya that could be used for animating character hair, rope, etc.
To manage multiple hair systems in the scene, please refer to [HairSystemManager][1].

### Features
- Interactive rig layout
- Spline IK with multiple controls and length preservation
- Variable FK
- nHair Dynamics with key-framed animation as guide (attraction adjustable)
- Animation blend between key-framed and simulated result


### Requirements
- Maya 2013 and above

### Usage
- Copy the root folder`DynRigBuilder` into your maya script folder, make sure the folder name stay the same. 
An example file structure is as follows:
![example file structure](https://user-images.githubusercontent.com/8005230/47268127-bb336480-d544-11e8-9878-f25e6faa842e.jpg)

- Run the scripts below, and the UI will show up.
```python
import DynRigBuilder
DynRigBuilder.show() 
```

[Demo Video](https://vimeo.com/233948834)

### TODO
- volume preservation / squash&stretch
- import and export rig layout
- control shape editor

[1]:https://github.com/raina-wu/hairsystemmanager
