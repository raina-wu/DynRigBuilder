

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
- Copy `DynRigBuilder` folder into your maya script folder
- Run the scripts below, and the UI will show up.
```python
import DynRigBuilder
DynRigBuilder.show() 
```

![Demo Video](https://vimeo.com/233948834)

### TODO
- volume preservation / squash&stretch
- import and export rig layout
- control shape editor

[1]:https://github.com/raina-wu/hairsystemmanager
